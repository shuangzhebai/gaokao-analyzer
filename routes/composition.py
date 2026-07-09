"""组卷 RESTful API 路由。

- POST   /api/v1/composition/generate     一键组卷（异步，返回 task_id）
- GET    /api/v1/composition/task/:task_id  查组卷进度
- POST   /api/v1/composition/adjust        手动微调
- GET    /api/v1/composition/:id           获取组卷结果
- POST   /api/v1/composition/:id/export    导出
- POST   /api/v1/composition/templates     存为模板
- GET    /api/v1/composition/templates     模板列表
- GET    /api/v1/composition/alternatives/:qid  备选题
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

from engines.composition_engine import CompositionEngine, HAS_ORTOOLS
from services.composition_service import CompositionService

logger = logging.getLogger("gaokao")
router = APIRouter()

_composition_service: CompositionService | None = None


def get_composition_service() -> CompositionService:
    """获取 CompositionService 单例。"""
    global _composition_service
    if _composition_service is None:
        _composition_service = CompositionService(engine=CompositionEngine())
    return _composition_service


@router.post("/api/v1/composition/generate")
async def generate_composition(
    constraints: dict = Body(...),
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """一键组卷（异步，返回 task_id）。"""
    required = ["subject_id", "total_count", "difficulty_mean"]
    for key in required:
        if key not in constraints:
            raise HTTPException(status_code=400, detail=f"缺少必需字段: {key}")
    task_id = await service.generate(constraints)
    return {"task_id": task_id, "message": "组卷任务已提交"}


@router.get("/api/v1/composition/task/{task_id}")
async def get_task_status(
    task_id: str,
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """查询组卷任务进度。"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/api/v1/composition/adjust")
async def adjust_composition(
    composition_id: int = Body(...),
    changes: list[dict] = Body(...),
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """手动微调：换题/调序/改分。"""
    result = await service.adjust(composition_id, changes)
    return result


@router.get("/api/v1/composition/{composition_id}")
async def get_composition(
    composition_id: int,
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """获取组卷结果。"""
    result = await service.get_composition(composition_id)
    if not result:
        raise HTTPException(status_code=404, detail="组卷记录不存在")
    return result


@router.post("/api/v1/composition/{composition_id}/export")
async def export_composition(
    composition_id: int,
    fmt: str = Query("pdf", alias="format"),
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """导出试卷（PDF/Word）。"""
    if fmt == "pdf":
        data = await service.export_pdf(composition_id)
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename=composition_{composition_id}.pdf"})
    elif fmt == "word":
        data = await service.export_word(composition_id)
        return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename=composition_{composition_id}.docx"})
    raise HTTPException(status_code=400, detail=f"不支持的导出格式: {fmt}")


@router.post("/api/v1/composition/templates")
async def save_template(
    name: str = Body(...),
    constraints: dict = Body(...),
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """存为模板。"""
    template_id = await service.save_template(name, constraints)
    return {"id": template_id, "message": "模板已保存"}


@router.get("/api/v1/composition/templates")
async def list_templates(
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """模板列表。"""
    templates = await service.list_templates()
    return templates


@router.get("/api/v1/composition/alternatives/{question_id}")
async def get_alternatives(
    question_id: int,
    n: int = Query(3, ge=1, le=10),
    service: CompositionService = Depends(get_composition_service),
) -> Any:
    """获取备选题。"""
    alt_ids = await service.get_alternatives(question_id, n=n)
    return {"question_id": question_id, "alternatives": alt_ids}
