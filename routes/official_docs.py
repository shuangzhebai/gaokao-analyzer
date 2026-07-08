"""
官方文件库路由（T03）
包含：文件列表、分类、刷新。
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from deps import get_official_docs

router = APIRouter()


@router.get("/api/official-docs")
async def list_official_docs(
    keyword: str = "",
    category: str = "",
    year: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    official_docs: Any = Depends(get_official_docs),
) -> Any:
    return await official_docs.search_docs(
        keyword=keyword, category=category, year=year, page=page, size=size,
    )


@router.get("/api/official-docs/categories")
async def list_doc_categories(official_docs: Any = Depends(get_official_docs)) -> Any:
    return await official_docs.get_categories()


@router.post("/api/official-docs/refresh")
async def refresh_official_docs(official_docs: Any = Depends(get_official_docs)) -> Any:
    result = await official_docs.refresh_from_official_sources()
    return result
