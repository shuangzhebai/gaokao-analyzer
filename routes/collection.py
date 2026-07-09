"""
采集进度与统计路由（v8.5）
提供采集统计、目标进度、手动触发等 API 端点。
"""
import logging
from typing import Any, Optional

from aiosqlite import Connection
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from models import get_db
from deps import get_auto_scraper, get_collection_service

logger = logging.getLogger("gaokao")
router = APIRouter()


@router.get("/api/v1/collection/stats")
async def collection_stats(
    db: Connection = Depends(get_db),
    service: Any = Depends(get_collection_service),
) -> Any:
    """获取采集统计：总题目数 / 各来源占比 / 各学科占比 / 近期趋势

    Returns:
        采集统计数据字典
    """
    try:
        stats = await service.get_collection_stats(db)
        return stats
    except Exception as e:
        logger.exception("Failed to get collection stats")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/collection/trigger")
async def trigger_collection(
    background_tasks: BackgroundTasks,
    db: Connection = Depends(get_db),
    auto_scraper: Any = Depends(get_auto_scraper),
    service: Any = Depends(get_collection_service),
) -> Any:
    """手动触发一次采集任务（异步执行）

    使用 BackgroundTasks 确保请求快速返回，实际采集在后台运行。
    """
    if not auto_scraper:
        raise HTTPException(status_code=500, detail="Auto-scraper not initialized")

    # 在后台任务中执行采集
    async def _run_collection():
        try:
            result = await service.trigger_manual_collection(db, auto_scraper)
            if not result.get("triggered"):
                logger.error(f"Manual collection failed: {result.get('error')}")
        except Exception as e:
            logger.exception("Background collection task failed")

    background_tasks.add_task(_run_collection)

    return {
        "triggered": True,
        "message": "采集任务已提交，后台执行中",
    }


@router.get("/api/v1/collection/target")
async def collection_target(
    db: Connection = Depends(get_db),
    service: Any = Depends(get_collection_service),
) -> Any:
    """获取目标进度：1000 份模拟卷 + 近 5 年高考真题

    Returns:
        {
            "target": {"mock_papers": 1000, "real_exams_years": 5},
            "collected_mock_papers": N,
            "collected_real_exams": N,
            "mock_progress_pct": float,
            "real_progress_pct": float,
            "overall_progress_pct": float,
            "year_coverage": {year: count}
        }
    """
    try:
        progress = await service.get_target_progress(db)
        return progress
    except Exception as e:
        logger.exception("Failed to get collection target progress")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/v1/collection/logs")
async def collection_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Connection = Depends(get_db),
    service: Any = Depends(get_collection_service),
) -> Any:
    """获取采集任务记录列表

    Args:
        limit: 返回记录数上限（默认 50，最大 200）
        offset: 分页偏移

    Returns:
        采集日志记录列表
    """
    try:
        logs = await service.get_collection_logs(db, limit=limit, offset=offset)
        return {"data": logs, "total": len(logs), "limit": limit, "offset": offset}
    except Exception as e:
        logger.exception("Failed to get collection logs")
        raise HTTPException(status_code=500, detail=str(e)) from e
