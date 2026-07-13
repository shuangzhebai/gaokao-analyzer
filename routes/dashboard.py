"""P2: 数据看板 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime, timedelta

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert

router = APIRouter(prefix="/api/v1/dashboard", tags=["数据看板"])


@router.get("/stats")
async def get_dashboard_stats(
    days: int = Query(30, description="统计天数"),
    user: dict = Depends(get_current_user),
):
    """获取系统统计概览"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        stats = {}

        # 用户统计
        cursor = await db.execute("SELECT COUNT(*) as count FROM users")
        row = await cursor.fetchone()
        stats["total_users"] = row["count"] if row else 0

        # 活跃用户（30天内）
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT user_id) as count FROM user_streaks WHERE last_study_date>=?",
            (cutoff[:10],)
        )
        row = await cursor.fetchone()
        stats["active_users"] = row["count"] if row else 0

        # 试题统计
        cursor = await db.execute("SELECT COUNT(*) as count FROM questions")
        row = await cursor.fetchone()
        stats["total_questions"] = row["count"] if row else 0

        # 试卷统计
        cursor = await db.execute("SELECT COUNT(*) as count FROM papers")
        row = await cursor.fetchone()
        stats["total_papers"] = row["count"] if row else 0

        # 诊断统计
        cursor = await db.execute("SELECT COUNT(*) as count FROM agent_execution_logs")
        row = await cursor.fetchone()
        stats["total_analyses"] = row["count"] if row else 0

        # 平均掌握度
        cursor = await db.execute(
            "SELECT AVG(theta) as avg_theta FROM student_profiles"
        )
        row = await cursor.fetchone()
        stats["avg_theta"] = round(float(row["avg_theta"]), 2) if row and row["avg_theta"] else 0

        # 课程/作业统计
        cursor = await db.execute("SELECT COUNT(*) as count FROM courses")
        row = await cursor.fetchone()
        stats["total_courses"] = row["count"] if row else 0

        cursor = await db.execute("SELECT COUNT(*) as count FROM assignments")
        row = await cursor.fetchone()
        stats["total_assignments"] = row["count"] if row else 0

        return stats
    finally:
        await db.close()


@router.get("/trends")
async def get_learning_trends(
    days: int = Query(30),
    user: dict = Depends(get_current_user),
):
    """获取学习趋势数据"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # 每日诊断次数
        cursor = await db.execute(
            """SELECT DATE(created_at) as date, COUNT(*) as count
               FROM agent_execution_logs
               WHERE created_at >= DATE('now', ?)
               GROUP BY DATE(created_at)
               ORDER BY date""",
            (f"-{days} days",)
        )
        rows = await cursor.fetchall()
        daily_analyses = [{"date": r["date"], "count": r["count"]} for r in rows]

        # 每日注册用户
        cursor = await db.execute(
            """SELECT DATE(created_at) as date, COUNT(*) as count
               FROM users
               WHERE created_at >= DATE('now', ?)
               GROUP BY DATE(created_at)
               ORDER BY date""",
            (f"-{days} days",)
        )
        rows = await cursor.fetchall()
        daily_users = [{"date": r["date"], "count": r["count"]} for r in rows]

        return {
            "daily_analyses": daily_analyses,
            "daily_users": daily_users,
        }
    finally:
        await db.close()


@router.get("/learning-progress")
async def get_learning_progress(
    user: dict = Depends(get_current_user),
):
    """获取个人学习进度（供前端ECharts使用）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # 能力变化轨迹
        cursor = await db.execute(
            """SELECT created_at as date, theta
               FROM stage_assessments
               WHERE user_id=? AND theta IS NOT NULL
               ORDER BY created_at""",
            (user["id"],)
        )
        rows = await cursor.fetchall()
        theta_trace = [{"date": r["date"], "theta": r["theta"]} for r in rows]

        # 掌握度分布
        cursor = await db.execute(
            """SELECT kp_name, mastery
               FROM student_profiles
               WHERE user_id=?
               ORDER BY mastery""",
            (user["id"],)
        )
        rows = await cursor.fetchall()
        mastery = [{"name": r["kp_name"] if r["kp_name"] else f"kp_{i}",
                     "value": r["mastery"]} for i, r in enumerate(rows)]

        return {
            "theta_trace": theta_trace,
            "mastery_distribution": mastery,
        }
    finally:
        await db.close()
