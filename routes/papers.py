"""
试卷相关路由（T03）
包含：科目、试卷列表/详情/删除、上传、课标/质量分析、优质题、批量 IRT/模拟、
单卷 IRT/模拟、拟合分析、知识点、筛选元数据、仪表盘统计。

T01 重构：所有裸 SQL 已抽取到 repositories/，业务编排到 services/。
路由层仅保留 HTTP 编排（参数校验 + 调用 service + 序列化响应）。
"""
import json
from typing import Optional

from aiosqlite import Connection
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from models import get_db
from deps import (
    get_paper_service, get_analysis_service,
    get_irt_model, get_kp_mapper,
    get_simulator, get_fitting_analyzer, get_paper_parser,
    get_curriculum_analyzer, get_quality_scorer, get_dedup_engine, get_auto_scraper,
)
from config import SUBJECTS, PAPER_TYPES, SOURCE_PRIORITY_MAP, REGION_HIERARCHY
from services.paper_service import PaperService
from services.analysis_service import AnalysisService

router = APIRouter()


# ============ 科目相关 ============

@router.get("/api/subjects")
async def list_subjects():
    return [{"id": k, **v} for k, v in SUBJECTS.items()]


# ============ 试卷管理 ============

@router.get("/api/papers")
async def list_papers(
    subject: Optional[str] = None,
    paper_type: Optional[str] = None,
    year: Optional[int] = None,
    province: Optional[str] = None,
    analysis_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Connection = Depends(get_db),
    service: PaperService = Depends(get_paper_service),
):
    return await service.list_papers(
        db, subject=subject, paper_type=paper_type, year=year,
        province=province, analysis_status=analysis_status,
        page=page, size=size,
    )


@router.get("/api/papers/{paper_id}")
async def get_paper(
    paper_id: int,
    db: Connection = Depends(get_db),
    service: PaperService = Depends(get_paper_service),
):
    return await service.get_paper(db, paper_id)


@router.delete("/api/papers/{paper_id}")
async def delete_paper(
    paper_id: int,
    db: Connection = Depends(get_db),
    service: PaperService = Depends(get_paper_service),
):
    await service.delete_paper(db, paper_id)
    return {"ok": True}


# ============ 试卷上传（增加查重+地区校验） ============

@router.post("/api/papers/upload")
async def upload_paper(
    file: UploadFile = File(...),
    subject: str = Form("math"),
    paper_type: str = Form("school"),
    title: Optional[str] = Form(None),
    year: int = Form(2026),
    province: Optional[str] = Form(None),
    db: Connection = Depends(get_db),
    paper_parser=Depends(get_paper_parser),
    kp_mapper=Depends(get_kp_mapper),
    dedup_engine=Depends(get_dedup_engine),
    service: PaperService = Depends(get_paper_service),
):
    return await service.upload_paper(
        db, file, subject, paper_type, title, year, province,
        paper_parser, kp_mapper, dedup_engine,
    )


# ============ 课标契合度分析 ============

@router.post("/api/papers/{paper_id}/curriculum-analysis")
async def analyze_curriculum(
    paper_id: int,
    db: Connection = Depends(get_db),
    curriculum_analyzer=Depends(get_curriculum_analyzer),
    service: PaperService = Depends(get_paper_service),
):
    return await service.analyze_curriculum(db, paper_id, curriculum_analyzer)


# ============ 题目质量评估 ============

@router.post("/api/papers/{paper_id}/quality-analysis")
async def analyze_quality(
    paper_id: int,
    db: Connection = Depends(get_db),
    quality_scorer=Depends(get_quality_scorer),
    service: PaperService = Depends(get_paper_service),
):
    return await service.analyze_quality(db, paper_id, quality_scorer)


# ============ 优质题推荐 ============

@router.get("/api/quality-questions")
async def get_quality_questions(
    subject: Optional[str] = None,
    q_type: Optional[str] = None,
    min_score: float = 85,
    limit: int = 50,
    db: Connection = Depends(get_db),
    service: PaperService = Depends(get_paper_service),
):
    return await service.get_quality_questions(
        db, subject=subject, q_type=q_type, limit=limit,
    )


# ============ 批量操作 ============

@router.post("/api/papers/batch/estimate-irt")
async def batch_estimate_irt(
    subject: Optional[str] = None,
    paper_type: Optional[str] = None,
    limit: int = 50,
    db: Connection = Depends(get_db),
    irt_model=Depends(get_irt_model),
    service: PaperService = Depends(get_paper_service),
):
    return await service.batch_estimate_irt(
        db, irt_model, subject=subject, paper_type=paper_type, limit=limit,
    )


@router.post("/api/papers/batch/simulate")
async def batch_simulate(
    subject: Optional[str] = None,
    n_students: Optional[int] = Query(None, le=500000),
    limit: int = 10,
    db: Connection = Depends(get_db),
    simulator=Depends(get_simulator),
    service: PaperService = Depends(get_paper_service),
):
    return await service.batch_simulate(
        db, simulator, subject=subject, n_students=n_students, limit=limit,
    )


# ============ IRT 参数估计 ============

@router.post("/api/papers/{paper_id}/estimate-irt")
async def estimate_irt(
    paper_id: int, n_sim_students: int = 5000,
    db: Connection = Depends(get_db),
    irt_model=Depends(get_irt_model),
    service: PaperService = Depends(get_paper_service),
):
    return await service.estimate_irt(db, paper_id, irt_model, n_sim_students)


# ============ 蒙特卡洛模拟 ============

@router.post("/api/papers/{paper_id}/simulate")
async def run_simulation(
    paper_id: int, n_students: Optional[int] = Query(None, le=500000),
    db: Connection = Depends(get_db),
    simulator=Depends(get_simulator),
    service: PaperService = Depends(get_paper_service),
):
    return await service.run_simulation(db, paper_id, simulator, n_students)


# ============ 拟合分析 ============

@router.post("/api/analysis/fit")
async def fit_analysis(
    sim_paper_id: int = Query(..., description="模拟卷 ID"),
    ref_paper_id: int = Query(..., description="真题 ID"),
    subject: str = Query("math"),
    db: Connection = Depends(get_db),
    fitting_analyzer=Depends(get_fitting_analyzer),
    simulator=Depends(get_simulator),
    service: PaperService = Depends(get_paper_service),
):
    return await service.fit_analysis(
        db, sim_paper_id, ref_paper_id, subject, fitting_analyzer, simulator,
    )


# ============ 知识点 ============

@router.get("/api/knowledge-points/{subject_id}")
async def list_knowledge_points(
    subject_id: str,
    db: Connection = Depends(get_db),
    service: AnalysisService = Depends(get_analysis_service),
):
    return await service.list_knowledge_points(db, subject_id)


# ============ 筛选元数据 ============

@router.get("/api/filters")
async def get_filter_options(
    db: Connection = Depends(get_db),
    service: PaperService = Depends(get_paper_service),
):
    return await service.get_filters(db)


# ============ 仪表盘统计 ============

@router.get("/api/dashboard")
async def dashboard_stats(
    db: Connection = Depends(get_db),
    auto_scraper=Depends(get_auto_scraper),
    service: PaperService = Depends(get_paper_service),
):
    return await service.get_dashboard(db, auto_scraper)
