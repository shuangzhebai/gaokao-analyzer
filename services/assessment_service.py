"""阶段测评服务 — CRUD+报告生成"""
from __future__ import annotations
from datetime import datetime
import json
from typing import Optional


class AssessmentService:
    def __init__(self, repo):
        self.repo = repo

    async def create(self, user_id: int, subject_id: str, session_id: str,
                      composition_id: int, theta_before: float,
                      learning_path_id: Optional[int] = None) -> int:
        return await self.repo.execute(
            """INSERT INTO stage_assessments
               (user_id, subject_id, session_id, composition_id,
                theta_before, learning_path_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'in_progress')""",
            user_id, subject_id, session_id, composition_id,
            theta_before, learning_path_id,
        )

    async def get_list(self, user_id: int, subject_id: Optional[str] = None) -> list[dict]:
        where = ["user_id = ?"]
        params = [user_id]
        if subject_id:
            where.append("subject_id = ?")
            params.append(subject_id)
        return await self.repo.query(
            f"SELECT * FROM stage_assessments WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            *params,
        )

    async def get_detail(self, assessment_id: int, user_id: int) -> Optional[dict]:
        rows = await self.repo.query(
            "SELECT * FROM stage_assessments WHERE id = ? AND user_id = ?",
            assessment_id, user_id,
        )
        if rows:
            row = rows[0]
            for json_field in ["weakness_before", "weakness_after", "weakness_resolved",
                               "diagnosis_json", "recommendations"]:
                val = row.get(json_field)
                if isinstance(val, str):
                    try:
                        row[json_field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            return row
        return None

    async def submit(self, assessment_id: int, user_id: int,
                      score: float, total_score: float,
                      theta_after: float, weakness_after: list,
                      diagnosis_json: dict, recommendations: list) -> None:
        """提交测评结果"""
        await self.repo.execute(
            """UPDATE stage_assessments SET
               score = ?, total_score = ?, theta_after = ?,
               theta_shift = ?,
               weakness_after = ?, diagnosis_json = ?,
               recommendations = ?, status = 'completed',
               completed_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            score, total_score, theta_after,
            theta_after - (await self._get_theta_before(assessment_id, user_id)),
            json.dumps(weakness_after, ensure_ascii=False),
            json.dumps(diagnosis_json, ensure_ascii=False),
            json.dumps(recommendations, ensure_ascii=False),
            assessment_id, user_id,
        )

    async def _get_theta_before(self, assessment_id: int, user_id: int) -> float:
        row = await self.repo.query(
            "SELECT theta_before FROM stage_assessments WHERE id = ? AND user_id = ?",
            assessment_id, user_id,
        )
        return row[0]["theta_before"] if row else 0.0

    async def get_report(self, assessment_id: int, user_id: int) -> Optional[dict]:
        """生成测评报告（含进步曲线数据）"""
        detail = await self.get_detail(assessment_id, user_id)
        if not detail:
            return None

        # 获取历史测评数据，画进步曲线
        history = await self.repo.query(
            """SELECT id, score, theta_after, completed_at
               FROM stage_assessments
               WHERE user_id = ? AND subject_id = ? AND status = 'completed'
               ORDER BY completed_at ASC""",
            user_id, detail.get("subject_id"),
        )

        return {
            "current": detail,
            "progress_curve": [
                {
                    "assessment_id": h["id"],
                    "score": h["score"],
                    "theta": h["theta_after"],
                    "completed_at": h["completed_at"],
                }
                for h in history
            ],
            "generated_at": datetime.now().isoformat(),
        }
