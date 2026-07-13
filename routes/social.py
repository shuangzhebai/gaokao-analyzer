"""P1: 排行榜 + 通知系统 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime, timedelta

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert

router = APIRouter(prefix="/api/v1/social", tags=["社交"])


# ─── 排行榜 ───

@router.get("/leaderboard")
async def get_leaderboard(
    period: str = Query("all", regex="^(daily|weekly|monthly|all)$"),
    limit: int = Query(20, le=100),
    user: dict = Depends(get_current_user),
):
    """获取排行榜（全站 / 日 / 周 / 月）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # 构建时间条件
        if period == "daily":
            date_filter = "AND us.last_study_date = DATE('now')"
        elif period == "weekly":
            date_filter = "AND us.last_study_date >= DATE('now', '-7 days')"
        elif period == "monthly":
            date_filter = "AND us.last_study_date >= DATE('now', '-30 days')"
        else:
            date_filter = ""

        cursor = await db.execute(
            f"""SELECT u.id as user_id, u.username,
                      COALESCE(us.current_streak, 0) as streak,
                      COALESCE(us.longest_streak, 0) as longest_streak,
                      COALESCE(us.total_study_days, 0) as total_days,
                      COALESCE(COUNT(DISTINCT ua.id), 0) as achievements,
                      COALESCE(AVG(sp.theta), 0) as avg_theta
               FROM users u
               LEFT JOIN user_streaks us ON u.id = us.user_id {date_filter}
               LEFT JOIN user_achievements ua ON u.id = ua.user_id
               LEFT JOIN student_profiles sp ON u.id = sp.user_id
               GROUP BY u.id
               ORDER BY streak DESC, total_days DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        rankings = []
        for i, r in enumerate(rows, 1):
            rankings.append({
                "rank": i,
                "user_id": r["user_id"],
                "username": r["username"],
                "streak": r["streak"],
                "longest_streak": r["longest_streak"],
                "total_study_days": r["total_days"],
                "achievements": r["achievements"],
                "avg_theta": round(float(r["avg_theta"]), 2) if r["avg_theta"] else 0,
            })

        return {
            "period": period,
            "rankings": rankings,
            "total": len(rankings),
        }
    finally:
        await db.close()


# ─── 通知系统 ───

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=100),
    user: dict = Depends(get_current_user),
):
    """获取用户通知"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        if unread_only:
            cursor = await db.execute(
                """SELECT * FROM notifications
                   WHERE user_id=? AND is_read=0
                   ORDER BY created_at DESC LIMIT ?""",
                (user["id"], limit)
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM notifications
                   WHERE user_id=?
                   ORDER BY created_at DESC LIMIT ?""",
                (user["id"], limit)
            )
        rows = await cursor.fetchall()
        return {"notifications": [dict(r) for r in rows]}
    finally:
        await db.close()


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    user: dict = Depends(get_current_user),
):
    """标记通知为已读"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        await db.execute(
            "UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",
            (notification_id, user["id"])
        )
        await db.commit()
        return {"status": "read"}
    finally:
        await db.close()


@router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    """标记全部已读"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        await db.execute(
            "UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0",
            (user["id"],)
        )
        await db.commit()
        return {"status": "all_read"}
    finally:
        await db.close()


async def create_notification(db, user_id: int, title: str, content: str,
                               notification_type: str = "system", link: str = ""):
    """创建通知（工具函数，供其他模块使用）"""
    await db.execute(
        """INSERT INTO notifications
           (user_id, title, content, notification_type, link)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, title, content, notification_type, link)
    )
