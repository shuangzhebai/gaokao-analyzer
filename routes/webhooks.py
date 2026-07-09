"""
Webhook 管理路由（差距项 #9）。
允许用户注册 webhook URL，在任务完成时自动推送通知。

P1-6: 新增 HMAC 签名 + SSRF 防护：
  - 发送前添加 X-Hub-Signature-256 签名头
  - 限制目标 URL 格式并禁止内网地址
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException

from config import WEBHOOK_ALLOWED_DOMAINS, WEBHOOK_SECRET
from deps import get_current_user, get_db

logger = logging.getLogger("gaokao")
router = APIRouter()

# URL 格式校验正则：仅允许 http/https，禁止 IP 直连内网
_WEBHOOK_URL_PATTERN = re.compile(r"^(https?://)([a-zA-Z0-9.-]+)(:\d+)?(/.*)?$")
# 内网 IP 前缀/域名黑名单
_INTERNAL_BLACKLIST = ("127.0.0.1", "localhost", "0.0.0.0", "::1")


def _is_internal_url(url: str) -> bool:
    """检查 URL 是否指向内网地址（SSRF 防护）。"""
    match = _WEBHOOK_URL_PATTERN.match(url)
    if not match:
        return True  # 格式不合法，视为不安全
    hostname = match.group(2).lower()

    # 域名黑名单检查
    if hostname in _INTERNAL_BLACKLIST:
        return True
    if hostname.startswith("10.") or hostname.startswith("172.16.") or hostname.startswith("192.168."):
        return True
    if hostname == "127" or hostname.endswith(".internal") or hostname.endswith(".local"):
        return True

    # 尝试解析为 IP 并检查
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return True
    except ValueError:
        pass  # 不是纯 IP，视为域名

    # 如配置了允许域名白名单，则检查
    if WEBHOOK_ALLOWED_DOMAINS:
        return not any(hostname == d or hostname.endswith("." + d) for d in WEBHOOK_ALLOWED_DOMAINS)

    return False


def _compute_hmac_signature(body: bytes, secret: str) -> str:
    """计算 HMAC-SHA256 签名。"""
    if not secret:
        return ""
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


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
    # P1-6: SSRF 防护 — 校验 URL 格式并禁止内网地址
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="仅支持 HTTPS 回调 URL")
    if len(url) > 500:
        raise HTTPException(status_code=400, detail="URL 过长")
    if _is_internal_url(url):
        raise HTTPException(status_code=400, detail="不允许指向内网地址的 Webhook URL")
    
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
        # P1-6: SSRF 防护 — 跳过内网目标 URL
        url = wh["url"]
        if _is_internal_url(url):
            logger.warning("Webhook %s 被跳过（内网地址）", url)
            continue

        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "gaokao-analyzer-webhook/1.0",
            }
            # P1-6: HMAC 签名
            if WEBHOOK_SECRET:
                signature = _compute_hmac_signature(body.encode("utf-8"), WEBHOOK_SECRET)
                if signature:
                    headers["X-Hub-Signature-256"] = signature

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    content=body,
                    headers=headers,
                )
                logger.info("Webhook %s -> %s: %d", url, event, resp.status_code)
        except Exception as e:
            logger.warning("Webhook %s failed: %s", url, e)
