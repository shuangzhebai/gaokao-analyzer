"""
采集相关路由（T03/T05）
包含：采集状态、采集落库(collect_papers)、自动采集状态/手动触发。
- B-2：collect_papers 不再计算指向不存在文件的 file_path，统一置 None（避免死引用/大文件 IO）
- R-6：trigger_auto_scrape 改用 BackgroundTasks，并记录异常兜底日志（避免火忘式 fire-and-forget）
"""
import logging
from typing import Optional

from aiosqlite import Connection
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from models import get_db
from deps import get_scraper_manager, get_dedup_engine, get_auto_scraper
from region_validator import RegionValidator

logger = logging.getLogger("gaokao")
router = APIRouter()


@router.get("/api/scrape/status")
async def scrape_status(db: Connection = Depends(get_db), auto_scraper=Depends(get_auto_scraper)):
    total = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
    by_type = await db.execute_fetchall(
        "SELECT paper_type, COUNT(*) as cnt FROM papers GROUP BY paper_type"
    )
    by_subject = await db.execute_fetchall(
        "SELECT subject_id, COUNT(*) as cnt FROM papers GROUP BY subject_id"
    )
    by_year = await db.execute_fetchall(
        "SELECT year, COUNT(*) as cnt FROM papers GROUP BY year ORDER BY year"
    )
    by_province = await db.execute_fetchall(
        "SELECT province, COUNT(*) as cnt FROM papers WHERE province IS NOT NULL GROUP BY province ORDER BY cnt DESC LIMIT 20"
    )
    by_priority = await db.execute_fetchall(
        "SELECT source_priority, COUNT(*) as cnt FROM papers GROUP BY source_priority"
    )
    dedup_stats = await db.execute_fetchall(
        "SELECT dedup_status, COUNT(*) as cnt FROM papers GROUP BY dedup_status"
    )
    recent_logs = await db.execute_fetchall(
        "SELECT * FROM scrape_logs ORDER BY created_at DESC LIMIT 20"
    )
    return {
        "total_papers": total["cnt"] if total else 0,
        "by_type": {r["paper_type"]: r["cnt"] for r in by_type},
        "by_subject": {r["subject_id"]: r["cnt"] for r in by_subject},
        "by_year": {str(r["year"]): r["cnt"] for r in by_year},
        "top_provinces": {r["province"]: r["cnt"] for r in by_province},
        "by_priority": {r["source_priority"]: r["cnt"] for r in by_priority},
        "dedup_stats": {r["dedup_status"]: r["cnt"] for r in dedup_stats},
        "recent_logs": recent_logs,
        "auto_scraper_status": auto_scraper.get_status() if auto_scraper else None,
    }


@router.post("/api/scrape/collect")
async def collect_papers(
    year: int = 2026,
    subjects: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Connection = Depends(get_db),
    scraper_manager=Depends(get_scraper_manager),
    dedup_engine=Depends(get_dedup_engine),
):
    sub_list = subjects.split(",") if subjects else None
    results = await scraper_manager.collect_all(year, sub_list, keyword=keyword or "")

    saved = []
    skipped = []
    for item in results:
        if "error" in item:
            await db.execute(
                "INSERT INTO scrape_logs (source_id, url, status, error_msg) VALUES (?,?,?,?)",
                (item.get("source_id"), "", "error", item.get("error", "")),
            )
            continue

        dedup_result = await dedup_engine.check_duplicate(
            title=item.get("title", ""),
            subject_id=item.get("subject", "math"),
            year=item.get("year", year),
            source_url=item.get("url", ""),
        )

        if dedup_result["status"] == "duplicate":
            await db.execute(
                "INSERT INTO scrape_logs (source_id, url, status, dedup_result) VALUES (?,?,?,?)",
                (item.get("source_id"), item.get("url"), "skipped", "duplicate"),
            )
            skipped.append(item.get("title"))
            continue

        existing = await db.execute_fetchone(
            "SELECT id FROM papers WHERE source_url = ?", (item.get("url"),)
        )
        if existing:
            continue

        # B-2: 仅落库元数据，不下载文件（避免指向不存在文件的死引用与大文件 IO）
        file_path = None

        content_hash = dedup_result.get("content_hash", "")
        dedup_status = dedup_result["status"]

        # v5.1: 地区校验
        region_result = RegionValidator.validate_region(
            province=item.get("province", ""),
            title=item.get("title", ""),
        )
        corrected_province = region_result["province"] or item.get("province")

        cursor = await db.execute(
            """INSERT INTO papers
               (title, subject_id, paper_type, source_id, source_url, year, province,
                file_path, analysis_status, content_hash, dedup_status, source_priority,
                collected_at, collector)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, datetime('now'), 'system')""",
            (
                item.get("title", ""),
                item.get("subject", "math"),
                item.get("type", "school"),
                item.get("source_id", ""),
                item.get("url", ""),
                item.get("year", year),
                corrected_province,
                file_path,
                content_hash,
                dedup_status,
                item.get("priority", "B"),
            ),
        )
        paper_id = cursor.lastrowid
        saved.append(paper_id)

        for sp in dedup_result.get("similar_papers", []):
            await db.execute(
                """INSERT INTO dedup_records (paper_id_1, paper_id_2, similarity, method, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (paper_id, sp["paper_id"], sp["similarity"], sp["method"], "pending"),
            )

        await db.execute(
            "INSERT INTO scrape_logs (source_id, url, status, paper_id, dedup_result) VALUES (?,?,?,?,?)",
            (item.get("source_id"), item.get("url"), "success", paper_id, dedup_status),
        )

    await db.commit()
    return {
        "found": len(results),
        "saved": len(saved),
        "skipped_duplicates": len(skipped),
        "paper_ids": saved,
    }


@router.get("/api/auto-scraper/status")
async def auto_scraper_status(auto_scraper=Depends(get_auto_scraper)):
    if not auto_scraper:
        return {"running": False, "error": "Auto-scraper not initialized"}
    return auto_scraper.get_status()


@router.post("/api/auto-scraper/trigger")
async def trigger_auto_scrape(
    background_tasks: BackgroundTasks,
    auto_scraper=Depends(get_auto_scraper),
):
    """手动触发一次自动采集（R-6：使用 BackgroundTasks，异常有兜底日志）"""
    if not auto_scraper:
        raise HTTPException(500, "Auto-scraper not initialized")
    background_tasks.add_task(_safe_run_once, auto_scraper)
    return {"triggered": True}


async def _safe_run_once(auto_scraper) -> None:
    """包裹自动采集单次运行，捕获并记录异常，避免任务静默失败。"""
    try:
        await auto_scraper._run_once()
    except Exception:  # noqa: BLE001
        logger.exception("手动触发的自动采集失败")
