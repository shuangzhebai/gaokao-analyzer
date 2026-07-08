"""
分析业务层：封装 IRT 估计、模拟、拟合分析、课标分析、质量分析、批量分析等业务编排。
每个方法第一个参数为 db（从路由层传入）。
"""
import json
from typing import Optional

import numpy as np
from fastapi import HTTPException

from repositories.paper_repo import PaperRepository
from repositories.question_repo import QuestionRepository
from repositories.analysis_repo import AnalysisRepository


class AnalysisService:
    """试卷分析业务服务"""

    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        question_repo: QuestionRepository,
        paper_repo: PaperRepository,
    ):
        self.analysis_repo = analysis_repo
        self.question_repo = question_repo
        self.paper_repo = paper_repo

    async def load_paper_for_analysis(self, db, paper_id: int):
        """从 DB 读取试卷与题目，构建可分析的 paper dict。"""
        paper = await self.paper_repo.get_by_id(db, paper_id)
        if not paper:
            return None, None
        rows = await self.question_repo.list_by_paper(db, paper_id)
        questions = []
        for q in rows:
            kps = json.loads(q["knowledge_points"]) if q["knowledge_points"] else []
            options = json.loads(q["options"]) if q["options"] else []
            questions.append({
                "q_type": q["q_type"],
                "content": q["content"] or "",
                "score": q["score"] or 0.0,
                "knowledge_points": kps,
                "options": options,
                "answer": q.get("answer") or "",
                "irt_a": q.get("irt_a"),
                "irt_b": q.get("irt_b"),
                "irt_c": q.get("irt_c"),
            })
        paper_dict = {
            "title": paper.get("title", ""),
            "subject": paper.get("subject_id", "math"),
            "year": paper.get("year", 2026),
            "questions": questions,
        }
        return paper, paper_dict

    async def analyze_paper(self, db, paper_id: int, analyzer) -> dict:
        """分析单份试卷，返回结构化报告并落库。"""
        paper, paper_dict = await self.load_paper_for_analysis(db, paper_id)
        if paper is None:
            raise HTTPException(404, "试卷不存在")
        if not paper_dict["questions"]:
            raise HTTPException(400, "该试卷没有题目，无法分析")
        report = analyzer.analyze(paper_dict)
        await self._store_report(db, paper_id, report)
        return report

    async def _store_report(self, db, paper_id: int, report: dict) -> None:
        """将报告落库到 paper_reports，并标记试卷 analysis_status='analyzed'。"""
        composite = report.get("composite", {})
        report_json = json.dumps(report, ensure_ascii=False, default=_json_default)
        await self.analysis_repo.save_report(
            db, paper_id, report_json,
            composite.get("score"), composite.get("grade"),
        )
        await self.paper_repo.update_analysis_status(db, paper_id, "analyzed")
        await db.commit()

    async def get_paper_report(self, db, paper_id: int) -> dict:
        """获取某试卷最新一次分析报告。"""
        row = await self.analysis_repo.get_report(db, paper_id)
        if not row:
            raise HTTPException(404, "该试卷暂无分析报告")
        report = json.loads(row["report_json"]) if row["report_json"] else None
        return {
            "paper_id": paper_id,
            "composite_score": row.get("composite_score"),
            "grade": row.get("grade"),
            "created_at": row.get("created_at"),
            "report": report,
        }

    async def list_knowledge_points(self, db, subject_id: str) -> list[dict]:
        """获取某科目的知识点列表"""
        return await db.execute_fetchall(
            "SELECT * FROM knowledge_points WHERE subject_id = ? ORDER BY code",
            (subject_id,),
        )


def _json_default(obj):
    """numpy 类型序列化兜底。"""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)
