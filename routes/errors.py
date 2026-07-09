"""错题库 RESTful API 路由。

- GET    /api/v1/errors             错题列表
- POST   /api/v1/errors             录入错题
- PUT    /api/v1/errors/:id         更新错题
- DELETE /api/v1/errors/:id         删除错题
- GET    /api/v1/errors/stats       统计分析
- GET    /api/v1/errors/diagnosis   薄弱诊断
- GET    /api/v1/errors/recommend/:qid  同类推荐
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from services.db_repository import ErrorRepository
from services.error_service import ErrorService
from services.student_profile import StudentProfileService

logger = logging.getLogger("gaokao")
router = APIRouter()

_error_service: ErrorService | None = None
_profile_service: StudentProfileService | None = None


def get_error_service() -> ErrorService:
    global _error_service
    if _error_service is None:
        _error_service = ErrorService(repo=ErrorRepository(db=None))  # type: ignore[arg-type]
    return _error_service


def get_profile_service() -> StudentProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = StudentProfileService(repo=ProfileRepository(db=None))  # type: ignore[arg-type]
    return _profile_service


@router.get("/api/v1/errors")
async def list_errors(
    user_id: int = Query(..., description="用户 ID"),
    subject_id: str | None = Query(None),
    error_reason: str | None = Query(None),
    is_mastered: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """错题列表（分页筛选）。"""
    filters: dict[str, Any] = {"user_id": user_id}
    if subject_id:
        filters["subject_id"] = subject_id
    if error_reason:
        filters["error_reason"] = error_reason
    if is_mastered is not None:
        filters["is_mastered"] = is_mastered
    db_gen = service._ensure_db()  # type: ignore[union-attr]
    db = await db_gen.__anext__()
    try:
        repo = service._repo  # type: ignore[union-attr]
        return await repo.list(filters, page=page, size=size)
    finally:
        await db.close()


@router.post("/api/v1/errors", status_code=201)
async def record_error(
    user_id: int = Body(...),
    question_id: int = Body(...),
    subject_id: str = Body(...),
    error_reason: str = Body("other"),
    user_score: float | None = Body(None),
    question_score: float = Body(0.0),
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """录入错题。"""
    result = await service.record_error(
        user_id, question_id, subject_id,
        error_reason=error_reason,
        user_score=user_score,
        question_score=question_score,
    )
    return result


@router.put("/api/v1/errors/{error_id}")
async def update_error(
    error_id: int,
    data: dict = Body(...),
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """更新错题（标记掌握等）。"""
    db = await service._ensure_db()  # type: ignore[union-attr]
    try:
        repo = service._repo  # type: ignore[union-attr]
        success = await repo.update(error_id, data)
        if not success:
            raise HTTPException(status_code=404, detail="错题记录不存在")
        return {"message": "更新成功"}
    finally:
        await db.close()


@router.delete("/api/v1/errors/{error_id}")
async def delete_error(
    error_id: int,
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """删除错题。"""
    db = await service._ensure_db()  # type: ignore[union-attr]
    try:
        repo = service._repo  # type: ignore[union-attr]
        success = await repo.delete(error_id)
        if not success:
            raise HTTPException(status_code=404, detail="错题记录不存在")
        return {"message": "删除成功"}
    finally:
        await db.close()


@router.get("/api/v1/errors/stats")
async def error_statistics(
    user_id: int = Query(...),
    subject_id: str | None = Query(None),
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """错题统计分析。"""
    return await service.get_statistics(user_id, subject_id=subject_id)


@router.get("/api/v1/errors/diagnosis")
async def weakness_diagnosis(
    user_id: int = Query(...),
    subject_id: str = Query(...),
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """薄弱知识点诊断。"""
    return await service.diagnose_weakness(user_id, subject_id)


@router.get("/api/v1/errors/recommend/{question_id}")
async def recommend_similar(
    question_id: int,
    n: int = Query(3, ge=1, le=10),
    service: ErrorService = Depends(get_error_service),
) -> Any:
    """同类错题推荐。"""
    return await service.recommend_similar(question_id, n=n)
