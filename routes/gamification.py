"""游戏化 + 知识图谱 API 路由 — v7.1 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert
import json

router = APIRouter(prefix="/api/v1/gamification", tags=["游戏化"])

# ─── 知识图谱 ───

@router.get("/knowledge-graph/{subject_id}")
async def get_knowledge_graph(
    subject_id: str,
    user: dict = Depends(get_current_user),
):
    """获取学科知识图谱（DAG）"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        cursor = await db.execute(
            "SELECT kp_code, kp_name, prerequisites, difficulty, exam_frequency, "
            "cognitive_level, importance, children, related_kps "
            "FROM knowledge_graph WHERE subject_id=?",
            (subject_id,)
        )
        rows = await cursor.fetchall()
        nodes = []
        for r in rows:
            nodes.append({
                "kp_code": r["kp_code"],
                "kp_name": r["kp_name"],
                "prerequisites": json.loads(r["prerequisites"] or "[]"),
                "difficulty": r["difficulty"],
                "exam_frequency": r["exam_frequency"],
                "cognitive_level": r["cognitive_level"],
                "importance": r["importance"],
                "children": json.loads(r["children"] or "[]"),
                "related_kps": json.loads(r["related_kps"] or "[]"),
            })
        return {"subject_id": subject_id, "nodes": nodes, "edges": _build_edges(nodes)}
    finally:
        await db.close()

def _build_edges(nodes: list) -> list:
    edges = []
    for n in nodes:
        for p in n.get("prerequisites", []):
            edges.append({"source": p, "target": n["kp_code"], "type": "prerequisite"})
        for c in n.get("children", []):
            edges.append({"source": n["kp_code"], "target": c, "type": "hierarchy"})
    return edges

# ─── 游戏化 ───

@router.get("/stats")
async def get_gamification_stats(user: dict = Depends(get_current_user)):
    """获取用户游戏化统计数据"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        streak = await _get_streak(db, user["id"])
        achievements = await _get_achievements(db, user["id"])
        return {
            "streak": streak,
            "achievements": achievements,
            "total_achievements": len(achievements),
        }
    finally:
        await db.close()

@router.post("/checkin")
async def daily_checkin(user: dict = Depends(get_current_user)):
    """每日学习打卡"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        today = date.today().isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO user_streaks (user_id, subject_id, last_study_date) "
            "VALUES (?, 'math', ?)",
            (user["id"], today)
        )
        await db.execute(
            "UPDATE user_streaks SET current_streak = current_streak + 1, "
            "total_study_days = total_study_days + 1, last_study_date = ? "
            "WHERE user_id = ? AND last_study_date < ?",
            (today, user["id"], today)
        )
        await db.execute(
            "UPDATE user_streaks SET longest_streak = MAX(longest_streak, current_streak) "
            "WHERE user_id = ?",
            (user["id"],)
        )
        await db.commit()
        streak = await _get_streak(db, user["id"])
        return {"status": "ok", "streak": streak, "checked_in": True}
    finally:
        await db.close()

async def _get_streak(db, user_id: int) -> dict:
    cursor = await db.execute(
        "SELECT current_streak, longest_streak, "
        "total_study_days, last_study_date "
        "FROM user_streaks WHERE user_id=? AND subject_id='math'",
        (user_id,)
    )
    row = await cursor.fetchone()
    if row:
        return {
            "current_streak": row["current_streak"],
            "longest_streak": row["longest_streak"],
            "total_study_days": row["total_study_days"],
            "last_study_date": row["last_study_date"],
        }
    return {"current_streak": 0, "longest_streak": 0, "total_study_days": 0}

async def _get_achievements(db, user_id: int) -> list:
    cursor = await db.execute(
        "SELECT achievement_code, achievement_name, description, "
        "icon_url, unlocked_at FROM user_achievements WHERE user_id=?",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
