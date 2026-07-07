"""
地区校验 / 审核 / 交叉验证 / 校准 路由（T03/T04）
包含：地区层级、地区校验、批量纠正、真实性审核、交叉验证、校准数据。
- T04：DeepSeek Key 改为运行时惰性读取 get_deepseek_key()
"""
import logging
from typing import Optional

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Query

from models import get_db
from config import REGION_HIERARCHY, CALIBRATION_DATA, get_deepseek_key
from region_validator import RegionValidator
from auth_verifier import AuthVerifier
from auto_scraper import CrossVerifier

logger = logging.getLogger("gaokao")
router = APIRouter()


# ============ 地区校验 API ============

@router.get("/api/regions")
async def get_regions():
    """获取地区层级映射"""
    return REGION_HIERARCHY


@router.get("/api/regions/validate")
async def validate_region(province: str = "", city: str = "", title: str = ""):
    """校验地区信息"""
    return RegionValidator.validate_region(province=province, city=city, title=title)


@router.post("/api/regions/batch-fix")
async def batch_fix_regions(limit: int = 100, db: Connection = Depends(get_db)):
    """批量纠正试卷地区信息"""
    rows = await db.execute_fetchall(
        "SELECT id, title, province, school FROM papers LIMIT ?", (limit,)
    )
    papers = [dict(r) for r in rows]

    results = RegionValidator.batch_validate(papers)
    fixed_count = 0

    for r in results:
        if r["auto_corrected"] and r["corrected_province"]:
            await db.execute(
                "UPDATE papers SET province = ? WHERE id = ?",
                (r["corrected_province"], r["paper_id"]),
            )
            fixed_count += 1
    await db.commit()

    return {"checked": len(results), "fixed": fixed_count, "details": results}


# ============ 真实性审核 API ============

@router.post("/api/audit/paper/{paper_id}")
async def audit_paper(paper_id: int):
    result = await AuthVerifier.audit_paper(
        paper_id, deepseek_key=get_deepseek_key()
    )
    return result


@router.post("/api/audit/batch")
async def batch_audit(limit: int = 100, unverified_only: bool = True):
    result = await AuthVerifier.batch_audit(limit=limit, unverified_only=unverified_only)
    return result


@router.get("/api/audit/summary")
async def audit_summary():
    return await AuthVerifier.get_audit_summary()


# ============ 交叉验证 API ============

@router.post("/api/verify/paper")
async def verify_paper_authenticity(
    title: str = Query(...),
    subject_id: str = Query(...),
    year: int = Query(...),
    province: str = "",
):
    result = await CrossVerifier.verify_paper(
        title=title, subject_id=subject_id, year=year, province=province,
        deepseek_key=get_deepseek_key(),
    )
    return result


# ============ 校准数据 API ============

@router.get("/api/calibration")
async def get_calibration_data():
    return CALIBRATION_DATA
