"""质量诊断 RESTful API 路由。

- POST   /api/v1/quality/analyze   分析题目/试卷质量
- POST   /api/v1/quality/batch     批量质量分析
- GET    /api/v1/quality/report/:id  获取质量报告
- GET    /api/v1/quality/compare   多卷横向对比
- POST   /api/v1/quality/precompute  触发 IRT 预计算
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from engines.hybrid_quality import HybridQualityEngine
from services.quality_service import QualityService

logger = logging.getLogger("gaokao")
router = APIRouter()

# 全局 service 单例
_quality_service: QualityService | None = None


def get_quality_service() -> QualityService:
    """获取 QualityService 单例。"""
    global _quality_service
    if _quality_service is None:
        _quality_service = QualityService(engine=HybridQualityEngine())
    return _quality_service


@router.post("/api/v1/quality/analyze")
async def analyze_quality(
    question_ids: list[int] = Body(..., embed=True),
    responses_data: list[dict] | None = Body(None, embed=True),
    service: QualityService = Depends(get_quality_service),
) -> Any:
    """分析题目/试卷质量。"""
    if not question_ids:
        raise HTTPException(status_code=400, detail="question_ids 不能为空")
    if len(question_ids) > 100:
        raise HTTPException(status_code=400, detail="单次最多分析 100 道题")
    return await service.analyze(question_ids, responses_data=responses_data)


@router.post("/api/v1/quality/batch")
async def batch_analyze(
    paper_ids: list[int] = Body(..., embed=True),
    service: QualityService = Depends(get_quality_service),
) -> Any:
    """批量质量分析（多份试卷）。"""
    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids 不能为空")
    return await service.batch_analyze(paper_ids)


@router.get("/api/v1/quality/report/{question_id}")
async def get_quality_report(
    question_id: int,
    service: QualityService = Depends(get_quality_service),
) -> Any:
    """获取单题质量报告。"""
    report = await service.get_report(question_id)
    if not report:
        raise HTTPException(status_code=404, detail="题目不存在或尚无质量数据")
    return report


@router.get("/api/v1/quality/compare")
async def compare_papers(
    paper_ids: str = Query(..., description="逗号分隔的试卷 ID"),
    service: QualityService = Depends(get_quality_service),
) -> Any:
    """多卷横向对比。"""
    ids = [int(x.strip()) for x in paper_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="paper_ids 不能为空")
    if len(ids) > 20:
        raise HTTPException(status_code=400, detail="最多对比 20 份试卷")
    return await service.compare_papers(ids)


@router.post("/api/v1/quality/precompute")
async def precompute_irt(
    service: QualityService = Depends(get_quality_service),
) -> Any:
    """触发 IRT 参数预计算。"""
    result = await service.precompute_all()
    return result
