"""
阶段二（后端核心）：试卷质量分析 API
- POST /api/papers/{id}/analyze      单卷分析（结构化报告，落库 paper_reports）
- POST /api/papers/analyze/batch     批量并行分析（接收 paper id 列表，返回报告数组）
- GET  /api/papers/{id}/report       取已存报告

T01 重构：所有裸 SQL 已抽取到 repositories/，业务编排到 services/。
"""
import json
import logging
from typing import Any, List, Optional

from aiosqlite import Connection
from fastapi import APIRouter, Body, Depends, HTTPException

from deps import get_paper_analyzer, get_analysis_service
from models import get_db
from paper_analysis import PaperAnalyzer, analyze_papers_batch
from services.analysis_service import AnalysisService

logger = logging.getLogger("gaokao")
router = APIRouter()


# ===================== 端点 =====================

@router.post("/api/papers/{paper_id}/analyze", include_in_schema=False)
@router.post("/api/v1/papers/{paper_id}/analyze")
async def analyze_paper_endpoint(
    paper_id: int,
    db: Connection = Depends(get_db),
    analyzer: PaperAnalyzer = Depends(get_paper_analyzer),
    service: AnalysisService = Depends(get_analysis_service),
) -> Any:
    """分析单份试卷，返回结构化报告并落库。"""
    return await service.analyze_paper(db, paper_id, analyzer)


@router.post("/api/papers/analyze/batch", include_in_schema=False)
@router.post("/api/v1/papers/analyze/batch")
async def analyze_papers_batch_endpoint(
    paper_ids: List[int] = Body(..., embed=True),
    max_workers: Optional[int] = None,
    db: Connection = Depends(get_db),
    analyzer: PaperAnalyzer = Depends(get_paper_analyzer),
    service: AnalysisService = Depends(get_analysis_service),
) -> Any:
    """批量并行分析多份试卷（接收 paper id 列表），返回与输入顺序一致的报告数组。"""
    if not paper_ids:
        raise HTTPException(400, "paper_ids 不能为空")

    # 读取所有试卷（保持输入顺序）
    loaded = []
    for pid in paper_ids:
        paper, paper_dict = await service.load_paper_for_analysis(db, pid)
        loaded.append((pid, paper_dict))

    # 仅对有题目的试卷做并行分析
    to_analyze = [(pid, pd) for pid, pd in loaded if pd and pd["questions"]]
    result_map = {}
    if to_analyze:
        papers = [pd for _pid, pd in to_analyze]
        subject = papers[0]["subject"] if papers else "math"
        reports = await analyze_papers_batch(
            papers, max_workers=max_workers, subject_id=subject, analyzer=analyzer
        )
        for (pid, _pd), rep in zip(to_analyze, reports):
            if "error" not in rep:
                await service._store_report(db, pid, rep)
            result_map[pid] = rep

    results = []
    for pid, pd in loaded:
        if pd is None:
            results.append({"paper_id": pid, "error": "试卷不存在"})
        elif not pd["questions"]:
            results.append({"paper_id": pid, "error": "该试卷没有题目，无法分析"})
        else:
            results.append({"paper_id": pid, "report": result_map.get(pid)})

    return {"count": len(results), "results": results}


@router.get("/api/papers/{paper_id}/report", include_in_schema=False)
@router.get("/api/v1/papers/{paper_id}/report")
async def get_paper_report(
    paper_id: int,
    db: Connection = Depends(get_db),
    service: AnalysisService = Depends(get_analysis_service),
) -> Any | None:
    """获取某试卷最新一次分析报告。"""
    return await service.get_paper_report(db, paper_id)
