"""
v5.0 真实性审核引擎
定期审核系统内试卷的真实性和数据一致性
"""
# mypy: disable-error-code="no-untyped-def,no-any-return,call-overload,operator,type-arg,assignment,var-annotated,misc,index,attr-defined,return-value,func-returns-value,return,has-type,unused-ignore,arg-type"
import json
import logging
import time
from datetime import datetime
from typing import Optional

from models import get_db
from region_validator import RegionValidator
from config import CALIBRATION_DATA, CITY_TO_PROVINCE, REGION_HIERARCHY

logger = logging.getLogger("gaokao")


class AuthVerifier:
    """真实性审核引擎"""

    @staticmethod
    async def audit_paper(paper_id: int, deepseek_key: str = "") -> dict:
        """审核单份试卷的真实性"""
        async for db in get_db():
            paper = await db.execute_fetchone(
                "SELECT * FROM papers WHERE id = ?", (paper_id,)
            )
            if not paper:
                return {"error": "试卷不存在"}

            issues = []
            score = 100  # 满分100，每发现一个问题扣分

            # 1. 地区校验
            region_result = RegionValidator.validate_region(
                province=paper.get("province", ""),
                city=paper.get("school", ""),
                title=paper.get("title", ""),
            )
            if not region_result["valid"]:
                score -= 20
                issues.append({
                    "type": "region_mismatch",
                    "severity": "high",
                    "message": f"地区校验失败: {'; '.join(region_result['errors'])}",
                    "auto_fix": region_result["auto_corrected"],
                })
            for warning in region_result.get("warnings", []):
                score -= 5
                issues.append({
                    "type": "region_warning",
                    "severity": "medium",
                    "message": warning,
                })

            # 2. 来源校验
            source_id = paper.get("source_id", "")
            source_url = paper.get("source_url", "")
            if not source_id and not source_url:
                score -= 15
                issues.append({
                    "type": "no_source",
                    "severity": "high",
                    "message": "试卷没有来源信息",
                })

            # 3. 题目完整性
            questions = await db.execute_fetchall(
                "SELECT * FROM questions WHERE paper_id = ?", (paper_id,)
            )
            q_count = paper.get("question_count", 0) or len(questions)
            if len(questions) == 0:
                score -= 10
                issues.append({
                    "type": "no_questions",
                    "severity": "medium",
                    "message": "试卷没有题目数据",
                })

            # 4. 分值合理性
            total_score = paper.get("total_score", 0) or 0
            if total_score > 0 and questions:
                actual_total = sum(q.get("score", 0) or 0 for q in questions)
                diff_pct = abs(actual_total - total_score) / total_score
                if diff_pct > 0.15:
                    score -= 10
                    issues.append({
                        "type": "score_mismatch",
                        "severity": "medium",
                        "message": f"题目总分({actual_total})与试卷总分({total_score})差距超过15%",
                    })

            # 5. IRT 参数合理性
            if questions:
                irt_count = sum(1 for q in questions if q.get("irt_a") is not None)
                if irt_count > 0:
                    avg_a = sum(q.get("irt_a", 0) or 0 for q in questions if q.get("irt_a") is not None) / irt_count
                    if avg_a < 0.5 or avg_a > 2.5:
                        score -= 10
                        issues.append({
                            "type": "irt_anomaly",
                            "severity": "medium",
                            "message": f"IRT区分度均值异常: {avg_a:.2f}（正常范围0.5-2.5）",
                        })

            # 6. 模拟结果与校准数据对比
            subject_id = paper.get("subject_id", "")
            cal = CALIBRATION_DATA.get(subject_id)
            if cal and questions:
                # 简单检查：题目的平均难度b值是否在合理范围
                b_values = [q.get("irt_b", 0) or 0 for q in questions if q.get("irt_b") is not None]
                if b_values:
                    avg_b = sum(b_values) / len(b_values)
                    # 正常高考难度均值在 -1 到 1 之间
                    if avg_b > 2.0 or avg_b < -2.0:
                        score -= 15
                        issues.append({
                            "type": "difficulty_anomaly",
                            "severity": "high",
                            "message": f"题目难度均值异常: {avg_b:.2f}（正常范围-2到2）",
                        })

            # 计算审核等级
            if score >= 90:
                audit_grade = "A"
                audit_status = "verified"
            elif score >= 75:
                audit_grade = "B"
                audit_status = "mostly_verified"
            elif score >= 60:
                audit_grade = "C"
                audit_status = "needs_review"
            else:
                audit_grade = "D"
                audit_status = "unverified"

            # 记录审核结果
            await db.execute(
                """INSERT INTO verification_audit
                   (paper_id, audit_type, score, grade, status, issues_json, audited_at, auditor)
                   VALUES (?, 'full', ?, ?, ?, ?, datetime('now'), 'system')""",
                (paper_id, score, audit_grade, audit_status,
                 json.dumps(issues, ensure_ascii=False)),
            )

            # 如果地区需要自动纠正
            if region_result["auto_corrected"] and region_result["province"]:
                await db.execute(
                    "UPDATE papers SET province = ?, verified = ? WHERE id = ?",
                    (region_result["province"], 1 if score >= 75 else 0, paper_id),
                )
            else:
                await db.execute(
                    "UPDATE papers SET verified = ? WHERE id = ?",
                    (1 if score >= 75 else 0, paper_id),
                )

            await db.commit()

            return {
                "paper_id": paper_id,
                "score": score,
                "grade": audit_grade,
                "status": audit_status,
                "issues": issues,
                "region_result": region_result,
            }

    @staticmethod
    async def batch_audit(limit: int = 100, unverified_only: bool = True) -> dict:
        """批量审核试卷"""
        async for db in get_db():
            conditions = []
            params = []

            if unverified_only:
                conditions.append("(verified = 0 OR verified IS NULL)")

            where = "WHERE " + " AND ".join(conditions) if conditions else ""

            rows = await db.execute_fetchall(
                f"SELECT id FROM papers {where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            )

            results = []
            for row in rows:
                result = await AuthVerifier.audit_paper(row["id"])
                results.append(result)

            # 统计
            grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
            for r in results:
                grade = r.get("grade", "D")
                grade_counts[grade] = grade_counts.get(grade, 0) + 1

            return {
                "total_audited": len(results),
                "grade_distribution": grade_counts,
                "results": results,
            }

    @staticmethod
    async def get_audit_summary() -> dict:
        """获取审核概况"""
        async for db in get_db():
            total = await db.execute_fetchone(
                "SELECT COUNT(*) as cnt FROM papers"
            )
            verified = await db.execute_fetchone(
                "SELECT COUNT(*) as cnt FROM papers WHERE verified = 1"
            )
            recent_audits = await db.execute_fetchall(
                """SELECT va.*, p.title
                   FROM verification_audit va
                   JOIN papers p ON va.paper_id = p.id
                   ORDER BY va.audited_at DESC LIMIT 20"""
            )
            grade_dist = await db.execute_fetchall(
                "SELECT grade, COUNT(*) as cnt FROM verification_audit GROUP BY grade"
            )

            return {
                "total_papers": total["cnt"] if total else 0,
                "verified_papers": verified["cnt"] if verified else 0,
                "unverified_papers": (total["cnt"] if total else 0) - (verified["cnt"] if verified else 0),
                "grade_distribution": {r["grade"]: r["cnt"] for r in grade_dist},
                "recent_audits": recent_audits,
            }
