"""
采集业务层：封装采集落库、状态查询等业务编排。
"""
import logging
from typing import Any, Optional

from region_validator import RegionValidator
from repositories.paper_repo import PaperRepository

logger = logging.getLogger("gaokao")

_MIN_YEAR = 2000
_MAX_YEAR = 2030


class ScrapeService:
    """采集业务服务"""

    def __init__(self, paper_repo: PaperRepository):
        self.paper_repo = paper_repo

    async def get_scrape_status(self, db: Any, auto_scraper: Any) -> dict[str, Any]:
        """获取采集状态统计"""
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

    async def collect_papers(
        self, db: Any, scraper_manager: Any, dedup_engine: Any,
        year: int = 2026,
        subjects: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict[str, Any]:
        """采集并落库试卷"""
        if year < _MIN_YEAR or year > _MAX_YEAR:
            raise ValueError(f"年份无效: {year}，需在 {_MIN_YEAR}-{_MAX_YEAR} 之间")

        sub_list = subjects.split(",") if subjects else None
        try:
            results = await scraper_manager.collect_all(year, sub_list, keyword=keyword or "")
        except Exception as e:
            logger.exception("采集失败: year=%s, subjects=%s", year, subjects)
            raise RuntimeError(f"采集过程出错: {e}") from e

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

            file_path = None
            content_hash = dedup_result.get("content_hash", "")
            dedup_status = dedup_result["status"]

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
