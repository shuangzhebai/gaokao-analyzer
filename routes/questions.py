"""题型库 RESTful API 路由。

- GET    /api/v1/questions         题库列表（分页+筛选）
- GET    /api/v1/questions/:id     题目详情
- POST   /api/v1/questions         新增题目（自动分类）
- PUT    /api/v1/questions/:id     更新题目
- DELETE /api/v1/questions/:id     删除题目
- POST   /api/v1/questions/classify  批量分类
- GET    /api/v1/questions/types   题型树
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from models import get_db
from services.db_repository import QuestionRepository
from services.question_service import QuestionService

logger = logging.getLogger("gaokao")
router = APIRouter()

# 全局 service 实例（轻量无状态）
_question_service: QuestionService | None = None


def get_question_service() -> QuestionService:
    """获取 QuestionService 单例。"""
    global _question_service
    if _question_service is None:
        repo = QuestionRepository(db=None)  # type: ignore[arg-type]
        _question_service = QuestionService(question_repo=repo)
    return _question_service


@router.get("/api/v1/questions")
async def list_questions(
    subject_id: str | None = Query(None, alias="subject_id"),
    question_type_id: int | None = Query(None, alias="question_type_id"),
    source: str | None = Query(None),
    year: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """题库列表（分页+筛选）。"""
    filters: dict[str, Any] = {}
    if subject_id:
        filters["subject_id"] = subject_id
    if question_type_id is not None:
        filters["question_type_id"] = question_type_id
    if source:
        filters["source"] = source
    if year is not None:
        filters["year"] = year
    return await service.list_questions(filters, page=page, size=size)


@router.get("/api/v1/questions/types")
async def get_question_types(
    subject_id: str | None = Query(None, alias="subject_id"),
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """获取题型树。"""
    return await service.get_question_types(subject_id=subject_id)


@router.post("/api/v1/questions/classify")
async def batch_classify(
    questions: list[dict] = Body(..., embed=True),
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """批量分类（不保存）。"""
    return await service.batch_classify(questions)


@router.get("/api/v1/questions/{question_id}")
async def get_question(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """题目详情（含分类信息）。"""
    question = await service.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return question


@router.post("/api/v1/questions", status_code=201)
async def create_question(
    question_data: dict = Body(...),
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """新增题目（自动分类）。"""
    question_id = await service.create_question(question_data)
    return {"id": question_id, "message": "创建成功"}


@router.put("/api/v1/questions/{question_id}")
async def update_question(
    question_id: int,
    question_data: dict = Body(...),
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """更新题目。"""
    success = await service.update_question(question_id, question_data)
    if not success:
        raise HTTPException(status_code=404, detail="题目不存在或未修改")
    return {"message": "更新成功"}


@router.delete("/api/v1/questions/{question_id}")
async def delete_question(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """删除题目。"""
    success = await service.delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"message": "删除成功"}


@router.get("/api/v1/questions/{question_id}/quality")
async def get_question_quality(
    question_id: int,
    service: QuestionService = Depends(get_question_service),
) -> Any:
    """单题质量摘要（IRT 参数 / CTT 指标）。"""
    summary = await service.get_quality_summary(question_id)
    if not summary:
        raise HTTPException(status_code=404, detail="题目不存在")
    return summary
