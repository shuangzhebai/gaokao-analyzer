"""F8: IRT间隔复习服务 — 错题复习调度"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import json
import math


def calculate_mastery_decay(mastery: float, days_since: int,
                            decay_rate: float = 0.05) -> float:
    """
    基于IRT的掌握度衰减函数
    公式: mastery(t) = mastery_0 × exp(-decay_rate × t)
    其中 t = 天数, decay_rate = 遗忘速率（默认0.05/天）

    答对一次: mastery += 0.15, decay_rate *= 0.7 (遗忘减慢)
    答错一次: mastery -= 0.10, decay_rate *= 1.3 (遗忘加速)
    """
    decay = mastery * math.exp(-decay_rate * days_since)
    return max(0.0, min(1.0, decay))


def calculate_next_review(current_interval: int, correct: bool) -> int:
    """
    计算下次复习间隔（天）
    答对 → 间隔翻倍（上限60天）
    答错 → 间隔减半（下限1天）
    """
    if correct:
        return min(current_interval * 2, 60)
    else:
        return max(current_interval // 2, 1)


def build_review_schedule(mastery_at_error: float,
                           initial_interval: int = 1) -> list[dict]:
    """
    构建复习时间表（四间隔）
    首次错 → 1天后
    第2次 → 3天后
    第3次 → 7天后
    第4次 → 30天后
    """
    intervals = [initial_interval, 3, 7, 30]
    schedule = []
    now = datetime.now()

    for i, interval_days in enumerate(intervals):
        review_time = now + timedelta(days=interval_days)
        schedule.append({
            "review_round": i + 1,
            "interval_days": interval_days,
            "scheduled_at": review_time.isoformat(),
            "completed": False,
        })

    return schedule


class ErrorReviewService:
    """F8: IRT间隔复习服务"""

    def __init__(self, db_repo, student_service):
        self.repo = db_repo
        self.student_service = student_service

    async def get_due_reviews(self, user_id: int, subject_id: str,
                               limit: int = 20) -> list[dict]:
        """
        获取到期待复习的错题列表
        WHERE next_review_at <= NOW() AND review_count < 4
        ORDER BY next_review_at ASC
        LIMIT limit
        """
        return await self.repo.query(
            """
            SELECT e.*, kp.name as kp_name
            FROM error_records e
            LEFT JOIN knowledge_points kp ON e.kp_code = kp.code
            WHERE e.user_id = ? AND e.next_review_at <= datetime('now')
                  AND e.review_count < 4
            ORDER BY e.next_review_at ASC
            LIMIT ?
            """,
            user_id, limit,
        )

    async def submit_review(self, record_id: int, user_id: int,
                             correct: bool) -> dict:
        """
        提交复习结果 → 更新掌握度+下次复习时间
        """
        record = await self.repo.get(record_id, table="error_records")
        if not record:
            return {"error": "record not found"}

        current_interval = record.get("review_interval_days", 1)
        current_mastery = record.get("mastery_at_last_review", 0.5)

        # 更新掌握度
        if correct:
            new_mastery = min(1.0, current_mastery + 0.15)
        else:
            new_mastery = max(0.0, current_mastery - 0.10)

        # 更新复习间隔
        new_interval = calculate_next_review(current_interval, correct)
        review_count = (record.get("review_count") or 0) + 1

        # 计算下次复习时间
        next_review = datetime.now() + timedelta(days=new_interval)

        # 构建复习计划JSON
        schedule_json = record.get("review_schedule", "[]")
        schedule = json.loads(schedule_json) if isinstance(schedule_json, str) else []
        schedule.append({
            "review_round": review_count,
            "interval_days": new_interval,
            "completed_at": datetime.now().isoformat(),
            "correct": correct,
        })

        await self.repo.execute(
            """
            UPDATE error_records SET
                mastery_at_last_review = ?,
                review_interval_days = ?,
                review_count = ?,
                next_review_at = ?,
                review_schedule = ?
            WHERE id = ? AND user_id = ?
            """,
            new_mastery, new_interval, review_count,
            next_review.isoformat(), json.dumps(schedule, ensure_ascii=False),
            record_id, user_id,
        )

        return {
            "record_id": record_id,
            "correct": correct,
            "mastery_before": current_mastery,
            "mastery_after": new_mastery,
            "next_review_in_days": new_interval,
            "review_count": review_count,
            "next_review_at": next_review.isoformat(),
            "total_reviews_completed": review_count,
        }

    async def get_review_stats(self, user_id: int) -> dict:
        """获取复习统计概览"""
        stats = await self.repo.query(
            """
            SELECT
                COUNT(*) as total_errors,
                SUM(CASE WHEN review_count >= 4 THEN 1 ELSE 0 END) as mastered_count,
                SUM(CASE WHEN next_review_at <= datetime('now') AND review_count < 4
                    THEN 1 ELSE 0 END) as due_reviews,
                AVG(CASE WHEN review_count > 0 THEN mastery_at_last_review ELSE NULL END)
                    as avg_mastery
            FROM error_records
            WHERE user_id = ?
            """,
            user_id,
        )
        return stats[0] if stats else {
            "total_errors": 0, "mastered_count": 0,
            "due_reviews": 0, "avg_mastery": None,
        }

    async def initialize_review_schedule(self, user_id: int,
                                          kp_code: str, mastery: float) -> None:
        """新错题首次录入时初始化复习计划"""
        schedule = build_review_schedule(mastery)
        next_review = datetime.now() + timedelta(days=1)
        await self.repo.execute(
            """
            UPDATE error_records SET
                review_schedule = ?,
                next_review_at = ?,
                review_interval_days = 1,
                review_count = 0,
                mastery_at_last_review = ?
            WHERE user_id = ? AND kp_code = ?
            """,
            json.dumps(schedule, ensure_ascii=False),
            next_review.isoformat(), mastery,
            user_id, kp_code,
        )
