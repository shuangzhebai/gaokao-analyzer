"""学习路径 + 教材映射 API 路由 — v7.0 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from ..deps import get_current_user

router = APIRouter(prefix="/api/v1/learning", tags=["学习中心"])


class PathUpdateRequest(BaseModel):
    progress_pct: Optional[float] = None
    status: Optional[str] = None


@router.get("/paths")
async def get_paths(
    subject_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """查询用户学习路径列表"""
    # TODO: inject LearningPathService
    return {"status": "ok", "data": []}


@router.get("/paths/{path_id}")
async def get_path_detail(path_id: int, user: dict = Depends(get_current_user)):
    """获取学习路径详情"""
    return {"path_id": path_id, "data": None}


@router.patch("/paths/{path_id}")
async def update_path(
    path_id: int,
    req: PathUpdateRequest,
    user: dict = Depends(get_current_user),
):
    """更新学习路径"""
    return {"path_id": path_id, "updated": True}


@router.delete("/paths/{path_id}")
async def delete_path(path_id: int, user: dict = Depends(get_current_user)):
    """废弃学习路径"""
    return {"path_id": path_id, "deleted": True}


@router.get("/progress")
async def get_learning_progress(
    subject_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取学习总览（仪表盘用）"""
    return {
        "status": "ok",
        "data": {
            "total_weak_points": 0,
            "mastered_kps": 0,
            "due_reviews": 0,
            "weekly_activity": [],
            "current_path": None,
        },
    }


# ============================================================
# F8: 待复习列表
# ============================================================

@router.get("/reviews")
async def get_reviews(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """F8: 获取到期待复习的错题列表"""
    return {"status": "ok", "data": [], "due_count": 0}


# ============================================================
# 教材映射
# ============================================================

@router.get("/textbook/subjects")
async def get_textbook_subjects():
    """获取有教材映射的科目列表"""
    return {"status": "ok", "data": []}


@router.get("/textbook/{subject_id}/textbooks")
async def get_textbooks(subject_id: str):
    """获取某科教材列表"""
    return {"subject_id": subject_id, "data": []}


@router.get("/textbook/{subject_id}/chapters")
async def get_chapters(subject_id: str, textbook: str = Query(None)):
    """获取章节树"""
    return {"subject_id": subject_id, "textbook": textbook, "data": []}


@router.get("/textbook/kp/{kp_code}")
async def get_kp_chapters(kp_code: str):
    """知识点反查教材章节"""
    return {"kp_code": kp_code, "data": []}
