"""
采集相关路由（T03/T05）
包含：采集状态、采集落库(collect_papers)、自动采集状态/手动触发。

T01 重构：所有裸 SQL 已抽取到 services/scrape_service.py。
"""
import logging
from typing import Any, Optional

from aiosqlite import Connection
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from models import get_db
from deps import get_scraper_manager, get_dedup_engine, get_auto_scraper, get_scrape_service
from services.scrape_service import ScrapeService

logger = logging.getLogger("gaokao")
router = APIRouter()


@router.get("/api/scrape/status", include_in_schema=False)
@router.get("/api/v1/scrape/status")
async def scrape_status(
    db: Connection = Depends(get_db),
    auto_scraper: Any = Depends(get_auto_scraper),
    service: ScrapeService = Depends(get_scrape_service),
) -> Any:
    return await service.get_scrape_status(db, auto_scraper)


@router.post("/api/scrape/collect", include_in_schema=False)
@router.post("/api/v1/scrape/collect")
async def collect_papers(
    year: int = 2026,
    subjects: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Connection = Depends(get_db),
    scraper_manager: Any = Depends(get_scraper_manager),
    dedup_engine: Any = Depends(get_dedup_engine),
    service: ScrapeService = Depends(get_scrape_service),
) -> Any:
    return await service.collect_papers(
        db, scraper_manager, dedup_engine,
        year=year, subjects=subjects, keyword=keyword,
    )


@router.get("/api/auto-scraper/status", include_in_schema=False)
@router.get("/api/v1/auto-scraper/status")
async def auto_scraper_status(auto_scraper: Any = Depends(get_auto_scraper)) -> Any:
    if not auto_scraper:
        return {"running": False, "error": "Auto-scraper not initialized"}
    return auto_scraper.get_status()


@router.post("/api/auto-scraper/trigger", include_in_schema=False)
@router.post("/api/v1/auto-scraper/trigger")
async def trigger_auto_scrape(
    background_tasks: BackgroundTasks,
    auto_scraper: Any = Depends(get_auto_scraper),
) -> Any:
    """手动触发一次自动采集（R-6：使用 BackgroundTasks，异常有兜底日志）"""
    if not auto_scraper:
        raise HTTPException(500, "Auto-scraper not initialized")
    background_tasks.add_task(_safe_run_once, auto_scraper)
    return {"triggered": True}


async def _safe_run_once(auto_scraper: Any) -> None:
    """包裹自动采集单次运行，捕获并记录异常，避免任务静默失败。"""
    try:
        await auto_scraper._run_once()
    except Exception:  # noqa: BLE001
        logger.exception("手动触发的自动采集失败")
