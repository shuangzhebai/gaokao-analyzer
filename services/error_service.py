"""错题库全链路服务：录入→分类→统计→诊断→推荐。"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from models import get_db
from services.db_repository import ErrorRepository, ProfileRepository

logger = logging.getLogger("gaokao")


class ErrorService:
    """错题服务。"""

    def __init__(
        self,
        repo: ErrorRepository | None = None,
        profile_service: Any = None,
    ) -> None:
        self._repo = repo or ErrorRepository(db=None)  # type: ignore[arg-type]
        self._profile = profile_service

    async def _ensure_db(self) -> Any:
        db_gen = get_db()
        db = await db_gen.__anext__()
        self._repo.db = db
        return db

    async def record_error(
        self,
        user_id: int,
        question_id: int,
        subject_id: str,
        error_reason: str = "other",
        user_score: float | None = None,
        question_score: float = 0.0,
    ) -> dict:
        """录入错题，同时更新学生画像。"""
        db = await self._ensure_db()
        try:
            # 1. 查是否已有记录
            cursor = await db.execute(
                "SELECT id, attempt_count FROM error_records WHERE user_id=? AND question_id=?",
                (user_id, question_id)
            )
            existing = await cursor.fetchone()

            if existing:
                # 2. 已有记录 → attempt_count +1
                record_id = existing["id"]
                attempt_count = existing["attempt_count"] + 1
                await self._repo.update(record_id, {
                    "attempt_count": attempt_count,
                    "user_score": user_score,
                    "error_reason": error_reason,
                })
                logger.info("错题记录已更新: id=%d, attempt=%d", record_id, attempt_count)
                return {"id": record_id, "status": "updated", "attempt_count": attempt_count}
            else:
                # 3. 无记录 → INSERT
                data = {
                    "user_id": user_id,
                    "question_id": question_id,
                    "subject_id": subject_id,
                    "error_reason": error_reason,
                    "user_score": user_score,
                    "question_score": question_score,
                    "attempt_count": 1,
                    "is_mastered": 0,
                }
                record_id = await self._repo.create(data)
                logger.info("错题已录入: id=%d, user=%d, question=%d", record_id, user_id, question_id)
                return {"id": record_id, "status": "recorded", "attempt_count": 1}
        finally:
            await db.close()

    async def get_statistics(self, user_id: int, subject_id: str | None = None) -> dict:
        """错题统计分析。"""
        db = await self._ensure_db()
        try:
            where = "user_id=?"
            params: list[Any] = [user_id]
            if subject_id:
                where += " AND subject_id=?"
                params.append(subject_id)

            # 总数
            cursor = await db.execute(f"SELECT COUNT(*) FROM error_records WHERE {where}", params)
            total = (await cursor.fetchone())[0]

            # 按学科
            cursor = await db.execute(
                "SELECT subject_id, COUNT(*) as cnt FROM error_records WHERE user_id=? GROUP BY subject_id",
                (user_id,)
            )
            by_subject = {r["subject_id"]: r["cnt"] for r in await cursor.fetchall()}

            # 按原因
            cursor = await db.execute(
                "SELECT error_reason, COUNT(*) as cnt FROM error_records WHERE user_id=? GROUP BY error_reason",
                (user_id,)
            )
            by_reason = {r["error_reason"]: r["cnt"] for r in await cursor.fetchall()}

            # 趋势（近30天）
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            cursor = await db.execute(
                """SELECT DATE(created_at) as dt, COUNT(*) as cnt
                   FROM error_records WHERE user_id=? AND created_at >= ?
                   GROUP BY DATE(created_at) ORDER BY dt""",
                (user_id, thirty_days_ago)
            )
            trend = [{"date": r["dt"], "count": r["cnt"]} for r in await cursor.fetchall()]

            return {
                "total_errors": total,
                "by_subject": by_subject,
                "by_reason": by_reason,
                "trend": trend,
            }
        finally:
            await db.close()

    async def diagnose_weakness(self, user_id: int, subject_id: str) -> dict:
        """薄弱知识点诊断（IRT θ + 知识图谱）。"""
        db = await self._ensure_db()
        try:
            # 获取学生画像
            cursor = await db.execute(
                "SELECT * FROM student_profiles WHERE user_id=? AND subject_id=?",
                (user_id, subject_id)
            )
            profile = await cursor.fetchone()

            theta = float(profile["theta"]) if profile else 0.0

            # 获取高频错题的知识点
            cursor = await db.execute(
                """SELECT e.question_id, e.attempt_count, q.knowledge_points, q.difficulty_tag
                   FROM error_records e
                   LEFT JOIN questions q ON e.question_id = q.id
                   WHERE e.user_id=? AND e.subject_id=? AND e.is_mastered=0
                   ORDER BY e.attempt_count DESC LIMIT 20""",
                (user_id, subject_id)
            )
            rows = await cursor.fetchall()

            # 提取知识点并统计（简化处理）
            kp_stats: dict[str, dict] = {}
            for r in rows:
                kps = (r["knowledge_points"] or "").split(",")
                for kp in kps:
                    kp = kp.strip()
                    if not kp:
                        continue
                    if kp not in kp_stats:
                        kp_stats[kp] = {"count": 0, "mastery": 0.5}
                    kp_stats[kp]["count"] += r["attempt_count"]

            # 按错题次数排序取 top5
            sorted_kps = sorted(kp_stats.items(), key=lambda x: -x[1]["count"])[:5]
            weaknesses = [
                {"knowledge_point": kp, "mastery": min(1.0, max(0.0, stats["mastery"]))}
                for kp, stats in sorted_kps
            ]

            suggestions = [
                f"建议重点复习 {w['knowledge_point']}（掌握度 {w['mastery']:.0%}）"
                for w in weaknesses
            ] if weaknesses else ["暂无薄弱知识点诊断数据，请继续练习"]

            return {
                "theta": round(theta, 4),
                "weakness_top5": weaknesses,
                "suggestions": suggestions,
            }
        finally:
            await db.close()

    async def recommend_similar(self, question_id: int, n: int = 3) -> list[dict]:
        """同类错题推荐（同知识点 + IRT 参数相似度）。"""
        db = await self._ensure_db()
        try:
            # 获取原题的知识点
            cursor = await db.execute(
                "SELECT knowledge_points, subject_id, irt_b, irt_a FROM questions WHERE id=?",
                (question_id,)
            )
            question = await cursor.fetchone()
            if not question:
                return []

            kps = (question["knowledge_points"] or "").split(",")
            subject_id = question["subject_id"]
            irt_b = question["irt_b"] or 0.0

            # 找同知识点题目（排除自身）
            similar: list[dict] = []
            for kp in kps:
                kp = kp.strip()
                if not kp:
                    continue
                cursor = await db.execute(
                    """SELECT id, content, irt_b, irt_a, difficulty_tag, score
                       FROM questions WHERE subject_id=? AND knowledge_points LIKE ?
                       AND id!=? ORDER BY ABS(irt_b - ?) LIMIT ?""",
                    (subject_id, f"%{kp}%", question_id, irt_b, n)
                )
                rows = await cursor.fetchall()
                for r in rows:
                    similar.append(dict(r))

            # 去重
            seen: set[int] = set()
            unique: list[dict] = []
            for r in similar:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    unique.append(r)

            return unique[:n]
        finally:
            await db.close()
