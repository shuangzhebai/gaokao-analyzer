"""
搜索相关路由（T03）
包含：全文搜索、搜索建议、题目搜索。
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from deps import get_search_engine

logger = logging.getLogger("gaokao")
router = APIRouter()


@router.get("/api/search", include_in_schema=False)
@router.get("/api/v1/search")
async def search_papers(
    q: str = "",
    subject: Optional[str] = None,
    paper_type: Optional[str] = None,
    year: Optional[int] = None,
    province: Optional[str] = None,
    exam_tag: Optional[str] = None,
    source_priority: Optional[str] = None,
    verified: Optional[bool] = None,
    analysis_status: Optional[str] = None,
    sort: str = "relevance",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search_engine: Any = Depends(get_search_engine),
) -> Any:
    return await search_engine.search(
        q=q, subject=subject, paper_type=paper_type, year=year,
        province=province, exam_tag=exam_tag, source_priority=source_priority,
        verified=verified, analysis_status=analysis_status,
        sort=sort, page=page, size=size,
    )


@router.get("/api/search/suggest", include_in_schema=False)
@router.get("/api/v1/search/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    search_engine: Any = Depends(get_search_engine),
) -> Any:
    suggestions = await search_engine.suggest(q, limit)
    return {"query": q, "suggestions": suggestions}


@router.get("/api/search/questions", include_in_schema=False)
@router.get("/api/v1/search/questions")
async def search_questions(
    q: str = Query(..., min_length=1),
    subject: Optional[str] = None,
    q_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search_engine: Any = Depends(get_search_engine),
) -> Any:
    return await search_engine.search_questions(
        q=q, subject=subject, q_type=q_type, page=page, size=size
    )
