"""
地区校验 / 审核 / 交叉验证 / 校准 路由（T03/T04）
包含：地区层级、地区校验、批量纠正、真实性审核、交叉验证、校准数据。

T01 重构：batch_fix_regions 的裸 SQL 已抽取到 services/paper_service.py。
"""
import logging
from typing import Any, Optional

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Query

from models import get_db
from config import REGION_HIERARCHY, CALIBRATION_DATA, get_deepseek_key
from region_validator import RegionValidator
from auth_verifier import AuthVerifier
from auto_scraper import CrossVerifier
from deps import get_paper_service
from services.paper_service import PaperService

logger = logging.getLogger("gaokao")
router = APIRouter()


# ============ 地区校验 API ============

@router.get("/api/regions", include_in_schema=False)
@router.get("/api/v1/regions")
async def get_regions() -> dict[str, Any]:
    """获取地区层级映射"""
    return REGION_HIERARCHY


@router.get("/api/regions/validate", include_in_schema=False)
@router.get("/api/v1/regions/validate")
async def validate_region(province: str = "", city: str = "", title: str = "") -> dict[str, Any]:
    """校验地区信息"""
    return RegionValidator.validate_region(province=province, city=city, title=title)


@router.post("/api/regions/batch-fix", include_in_schema=False)
@router.post("/api/v1/regions/batch-fix")
async def batch_fix_regions(
    limit: int = 100,
    db: Connection = Depends(get_db),
    service: PaperService = Depends(get_paper_service),
) -> dict[str, Any]:
    """批量纠正试卷地区信息"""
    return await service.batch_fix_regions(db, limit=limit)


# ============ 真实性审核 API ============

@router.post("/api/audit/paper/{paper_id}", include_in_schema=False)
@router.post("/api/v1/audit/paper/{paper_id}")
async def audit_paper(paper_id: int) -> dict[str, Any]:
    result = await AuthVerifier.audit_paper(
        paper_id, deepseek_key=get_deepseek_key()
    )
    return result


@router.post("/api/audit/batch", include_in_schema=False)
@router.post("/api/v1/audit/batch")
async def batch_audit(limit: int = 100, unverified_only: bool = True) -> dict[str, Any]:
    result = await AuthVerifier.batch_audit(limit=limit, unverified_only=unverified_only)
    return result


@router.get("/api/audit/summary", include_in_schema=False)
@router.get("/api/v1/audit/summary")
async def audit_summary() -> dict[str, Any]:
    return await AuthVerifier.get_audit_summary()


# ============ 交叉验证 API ============

@router.post("/api/verify/paper", include_in_schema=False)
@router.post("/api/v1/verify/paper")
async def verify_paper_authenticity(
    title: str = Query(...),
    subject_id: str = Query(...),
    year: int = Query(...),
    province: str = "",
) -> dict[str, Any]:
    result = await CrossVerifier.verify_paper(
        title=title, subject_id=subject_id, year=year, province=province,
        deepseek_key=get_deepseek_key(),
    )
    return result


# ============ 校准数据 API ============

@router.get("/api/calibration", include_in_schema=False)
@router.get("/api/v1/calibration")
async def get_calibration_data() -> dict[str, Any]:
    return CALIBRATION_DATA
