"""阶段测评 API 路由 — v7.0 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..deps import get_current_user

router = APIRouter(prefix="/api/v1/assessment", tags=["阶段测评"])


class AnswerItem(BaseModel):
    question_id: int | str
    answer: str | None = None
    correct: bool = False
    score: float = 0.0


class AssessmentSubmitRequest(BaseModel):
    answers: list[AnswerItem]


@router.get("/list")
async def get_assessment_list(
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """查询测评记录列表"""
    return {"status": "ok", "data": []}


@router.get("/{assessment_id}")
async def get_assessment_detail(
    assessment_id: int,
    user: dict = Depends(get_current_user),
):
    """获取测评详情"""
    return {"assessment_id": assessment_id, "data": None}


@router.post("/{assessment_id}/submit")
async def submit_assessment(
    assessment_id: int,
    req: AssessmentSubmitRequest,
    user: dict = Depends(get_current_user),
):
    """提交测评答题结果"""
    correct = sum(1 for a in req.answers if a.correct)
    total = len(req.answers) or 1
    score = round(correct / total * 100, 1) if total > 0 else 0

    return {
        "status": "ok",
        "data": {
            "assessment_id": assessment_id,
            "score": score,
            "total": total,
            "correct": correct,
            "submitted_at": datetime.now().isoformat(),
        },
    }


@router.get("/{assessment_id}/report")
async def get_assessment_report(
    assessment_id: int,
    user: dict = Depends(get_current_user),
):
    """获取测评报告（含进步曲线）"""
    return {
        "assessment_id": assessment_id,
        "report": {
            "score": None,
            "progress_curve": [],
            "weaknesses": [],
            "recommendations": [],
            "generated_at": datetime.now().isoformat(),
        },
    }
