"""P3: 多端同步 API 路由 — v7.2 新增"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime
import json

from ..deps import get_current_user
from ..helpers import db_one, db_all, db_exec, db_insert

router = APIRouter(prefix="/api/v1/sync", tags=["多端同步"])


class SyncPayload(BaseModel):
    device_id: str
    last_sync_at: Optional[str] = None
    data: dict[str, Any] = {}


@router.post("/upload")
async def sync_upload(
    payload: SyncPayload,
    user: dict = Depends(get_current_user),
):
    """上传本地数据并同步到服务端"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        now = datetime.now().isoformat()
        await db.execute(
            """INSERT OR REPLACE INTO sync_records
               (user_id, device_id, data_json, synced_at)
               VALUES (?, ?, ?, ?)""",
            (user["id"], payload.device_id,
             json.dumps(payload.data, ensure_ascii=False), now)
        )
        await db.commit()
        return {"status": "synced", "synced_at": now}
    finally:
        await db.close()


@router.get("/download")
async def sync_download(
    device_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """从服务端同步数据到本地设备"""
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        # 获取用户的所有同步数据
        cursor = await db.execute(
            """SELECT device_id, data_json, synced_at
               FROM sync_records
               WHERE user_id=? AND device_id != ?
               ORDER BY synced_at DESC""",
            (user["id"], device_id)
        )
        rows = await cursor.fetchall()

        # 获取用户最新的完整状态
        cursor2 = await db.execute(
            "SELECT theta, knowledge_mastery FROM student_profiles WHERE user_id=?",
            (user["id"],)
        )
        profile = await cursor2.fetchone()

        # 获取学习进度
        cursor3 = await db.execute(
            "SELECT current_streak, total_study_days FROM user_streaks WHERE user_id=?",
            (user["id"],)
        )
        streak = await cursor3.fetchone()

        return {
            "device_syncs": [dict(r) for r in rows],
            "profile": dict(profile) if profile else {},
            "streak": dict(streak) if streak else {},
            "synced_at": datetime.now().isoformat(),
        }
    finally:
        await db.close()
