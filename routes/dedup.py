"""
查重路由（T03）
包含：试卷查重检测。
"""
from typing import Any

from fastapi import APIRouter, Depends, Query

from deps import get_dedup_engine

router = APIRouter()


@router.post("/api/papers/dedup")
async def check_dedup(
    title: str = Query(..., min_length=1),
    subject_id: str = Query(...),
    year: int = Query(...),
    source_url: str = "",
    dedup_engine: Any = Depends(get_dedup_engine),
) -> Any:
    result = await dedup_engine.check_duplicate(
        title=title, subject_id=subject_id, year=year, source_url=source_url,
    )
    return result
