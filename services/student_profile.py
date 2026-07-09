"""学生画像 — IRT 能力值 + 知识图谱掌握度。"""

import json
import logging
from datetime import datetime
from typing import Any

from models import get_db
from services.db_repository import ProfileRepository

logger = logging.getLogger("gaokao")


class StudentProfileService:
    """学生画像服务。"""

    def __init__(self, repo: ProfileRepository | None = None) -> None:
        self._repo = repo or ProfileRepository(db=None)  # type: ignore[arg-type]

    async def _ensure_db(self) -> Any:
        db_gen = get_db()
        db = await db_gen.__anext__()
        self._repo.db = db
        return db

    async def get_theta(self, user_id: int, subject_id: str) -> float:
        """获取 IRT 能力值（缓存优先）。"""
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT theta FROM student_profiles WHERE user_id=? AND subject_id=?",
                (user_id, subject_id)
            )
            row = await cursor.fetchone()
            return float(row["theta"]) if row else 0.0
        finally:
            await db.close()

    async def update_knowledge_mastery(
        self,
        user_id: int,
        question_id: int,
        is_correct: bool,
        subject_id: str = "",
    ) -> None:
        """更新知识图谱掌握度（基于 Bayesian 估计）。"""
        db = await self._ensure_db()
        try:
            # 获取题目知识点
            cursor = await db.execute(
                "SELECT knowledge_points, subject_id FROM questions WHERE id=?",
                (question_id,)
            )
            q = await cursor.fetchone()
            if not q:
                return
            subject_id = q["subject_id"]

            # 获取现有画像
            cursor = await db.execute(
                "SELECT * FROM student_profiles WHERE user_id=? AND subject_id=?",
                (user_id, subject_id)
            )
            profile = await cursor.fetchone()

            if profile:
                knowledge_mastery: dict = json.loads(profile["knowledge_mastery"] or "{}")
                total_q = profile["total_questions"] + 1
                correct_q = profile["correct_questions"] + (1 if is_correct else 0)

                # 更新每个知识点的掌握度（Bayesian 平滑）
                kps = (q["knowledge_points"] or "").split(",")
                for kp in kps:
                    kp = kp.strip()
                    if not kp:
                        continue
                    if kp not in knowledge_mastery:
                        knowledge_mastery[kp] = {"attempts": 0, "correct": 0, "mastery": 0.5}
                    km = knowledge_mastery[kp]
                    km["attempts"] += 1
                    if is_correct:
                        km["correct"] += 1
                    # Beta-Binomial: (correct + 1) / (attempts + 2)
                    km["mastery"] = round((km["correct"] + 1) / (km["attempts"] + 2), 4)

                # 更新 theta（简化：按正确率映射）
                theta = (correct_q / max(total_q, 1)) * 2 - 1

                await db.execute(
                    """UPDATE student_profiles SET
                       theta=?, knowledge_mastery=?, total_questions=?, correct_questions=?,
                       last_updated=datetime('now')
                       WHERE user_id=? AND subject_id=?""",
                    (theta, json.dumps(knowledge_mastery, ensure_ascii=False),
                     total_q, correct_q, user_id, subject_id)
                )
            else:
                # 新建画像
                theta = 1.0 if is_correct else -1.0
                kps = (q["knowledge_points"] or "").split(",")
                knowledge_mastery = {}
                for kp in kps:
                    kp = kp.strip()
                    if kp:
                        knowledge_mastery[kp] = {
                            "attempts": 1,
                            "correct": 1 if is_correct else 0,
                            "mastery": 0.67 if is_correct else 0.33,
                        }
                await db.execute(
                    """INSERT INTO student_profiles
                       (user_id, subject_id, theta, theta_se, knowledge_mastery, total_questions, correct_questions)
                       VALUES (?, ?, ?, 1.0, ?, 1, ?)""",
                    (user_id, subject_id, theta,
                     json.dumps(knowledge_mastery, ensure_ascii=False),
                     1 if is_correct else 0)
                )

            await db.commit()
            logger.info("学生画像已更新: user=%d, subject=%s, correct=%s", user_id, subject_id, is_correct)
        finally:
            await db.close()

    async def get_knowledge_mastery(self, user_id: int, subject_id: str) -> dict:
        """获取知识掌握图谱。"""
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                "SELECT knowledge_mastery, theta FROM student_profiles WHERE user_id=? AND subject_id=?",
                (user_id, subject_id)
            )
            profile = await cursor.fetchone()
            if not profile:
                return {"theta": 0.0, "knowledge_mastery": {}}
            km = json.loads(profile["knowledge_mastery"] or "{}")
            return {
                "theta": round(float(profile["theta"]), 4),
                "knowledge_mastery": km,
            }
        finally:
            await db.close()

    async def upsert_profile(self, user_id: int, subject_id: str, data: dict) -> bool:
        """创建或更新学生画像。"""
        db = await self._ensure_db()
        try:
            existing = await self._repo.get_by_user_subject(user_id, subject_id)
            if existing:
                set_clause = ", ".join([f"{k}=?" for k in data.keys()])
                data["last_updated"] = datetime.utcnow().isoformat()
                await db.execute(
                    f"UPDATE student_profiles SET {set_clause} WHERE user_id=? AND subject_id=?",
                    (*data.values(), user_id, subject_id)
                )
            else:
                data["user_id"] = user_id
                data["subject_id"] = subject_id
                await self._repo.create(data)
            return True
        finally:
            await db.close()
