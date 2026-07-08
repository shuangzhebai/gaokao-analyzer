"""
Webhook 管理路由（差距项 #9）。
允许用户注册 webhook URL，在任务完成时自动推送通知。
"""
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from deps import get_current_user, get_db

logger = logging.getLogger("gaokao")
router = APIRouter()


@router.get("/api/webhooks", include_in_schema=False)
@router.get("/api/v1/webhooks")
async def list_webhooks(db: Any = Depends(get_db), user: dict = Depends(get_current_user)) -> list[dict]:
    """列出当前用户的所有 webhook。"""
    rows = await db.execute_fetchall(
        "SELECT id, url, events, created_at FROM webhooks WHERE user_id = ? ORDER BY created_at DESC",
        [user.get("sub", 0)]
    )
    return rows


@router.post("/api/webhooks", include_in_schema=False)
@router.post("/api/v1/webhooks")
async def create_webhook(
    url: str, events: str = "task.completed",
    db: Any = Depends(get_db), user: dict = Depends(get_current_user),
) -> dict:
    """注册一个新的 webhook。
    
    Args:
        url: 回调 URL
        events: 逗号分隔的事件类型，如 "task.completed,task.failed"
    """
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="仅支持 HTTPS 回调 URL")
    if len(url) > 500:
        raise HTTPException(status_code=400, detail="URL 过长")
    
    await db.execute(
        "INSERT INTO webhooks (user_id, url, events) VALUES (?, ?, ?)",
        [user.get("sub", 0), url, events]
    )
    await db.commit()
    return {"status": "created", "url": url, "events": events}


@router.delete("/api/webhooks/{webhook_id}", include_in_schema=False)
@router.delete("/api/v1/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: int, db: Any = Depends(get_db), user: dict = Depends(get_current_user),
) -> dict:
    """删除一个 webhook。"""
    await db.execute("DELETE FROM webhooks WHERE id = ? AND user_id = ?", [webhook_id, user.get("sub", 0)])
    await db.commit()
    return {"status": "deleted", "id": webhook_id}


async def trigger_webhooks(db: Any, event: str, payload: dict) -> None:
    """触发匹配事件类型的 webhooks（异步通知）。
    
    在任务完成/失败时调用。例如:
    await trigger_webhooks(db, "task.completed", {"task_id": "...", "result": {...}})
    """
    rows = await db.execute_fetchall(
        "SELECT id, url, events FROM webhooks WHERE instr(events, ?) > 0",
        [event]
    )
    if not rows:
        return
    
    body = json.dumps({"event": event, "payload": payload}, ensure_ascii=False, default=str)
    
    for wh in rows:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    wh["url"],
                    content=body,
                    headers={"Content-Type": "application/json", "User-Agent": "gaokao-analyzer-webhook/1.0"},
                )
                logger.info("Webhook %s -> %s: %d", wh["url"], event, resp.status_code)
        except Exception as e:
            logger.warning("Webhook %s failed: %s", wh["url"], e)
