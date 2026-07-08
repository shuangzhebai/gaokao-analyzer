"""
分析结果 DAO：封装 analysis_results 和 paper_reports 表的所有 SQL 操作。
"""
import json
from typing import Optional


class AnalysisRepository:
    """分析结果数据访问对象"""

    async def get_by_paper(self, db, paper_id: int) -> list[dict]:
        """获取某试卷的所有分析结果"""
        return await db.execute_fetchall(
            "SELECT * FROM analysis_results WHERE paper_id = ?", (paper_id,)
        )

    async def create(self, db, data: dict) -> int:
        """插入一条分析结果记录"""
        cursor = await db.execute(
            """INSERT INTO analysis_results
               (paper_id, ref_paper_id, fit_score, knowledge_coverage,
                difficulty_ks_stat, difficulty_ks_pvalue, question_type_match,
                quality_score, simulation_mean, simulation_std, simulation_median,
                simulation_json, score_distribution_json, analysis_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("paper_id"),
                data.get("ref_paper_id"),
                data.get("fit_score"),
                data.get("knowledge_coverage"),
                data.get("difficulty_ks_stat"),
                data.get("difficulty_ks_pvalue"),
                data.get("question_type_match"),
                data.get("quality_score"),
                data.get("simulation_mean"),
                data.get("simulation_std"),
                data.get("simulation_median"),
                data.get("simulation_json"),
                data.get("score_distribution_json"),
                data.get("analysis_json"),
            ),
        )
        return cursor.lastrowid

    async def save_report(self, db, paper_id: int, report_json: str, score: Optional[float], grade: Optional[str]) -> None:
        """保存分析报告到 paper_reports 表"""
        await db.execute(
            """INSERT INTO paper_reports (paper_id, report_json, composite_score, grade)
               VALUES (?, ?, ?, ?)""",
            (paper_id, report_json, score, grade),
        )

    async def get_report(self, db, paper_id: int) -> Optional[dict]:
        """获取某试卷最新一份分析报告"""
        return await db.execute_fetchone(
            "SELECT * FROM paper_reports WHERE paper_id = ? ORDER BY id DESC LIMIT 1",
            (paper_id,),
        )
