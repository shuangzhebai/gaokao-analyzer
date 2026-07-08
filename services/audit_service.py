"""
操作审计日志业务层：封装审计日志写入与查询逻辑。
与 verification_audit（试卷真实性审核）完全独立。
"""
import json
from typing import Any, Optional

from repositories.audit_repo import AuditRepository


class AuditService:
    """操作审计日志业务服务"""

    def __init__(self, audit_repo: AuditRepository):
        self.audit_repo = audit_repo

    async def log(
        self,
        db: Any,
        user: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        """写入一条审计日志。

        Args:
            db: aiosqlite 连接。
            user: 操作者用户名，None 或空字符串时回退为 "anonymous"。
            action: HTTP 方法，如 POST / PUT / DELETE。
            resource_type: 被操作资源类型，如 'paper', 'question'。
            resource_id: 被操作资源的 ID（可选）。
            ip_address: 请求来源 IP（可选）。
            user_agent: 客户端 User-Agent（可选，超 500 字符自动截断）。
            detail: 额外上下文字典，自动序列化为 JSON（可选）。
        """
        entry = {
            "user": user or "anonymous",
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "ip_address": ip_address or "",
            "user_agent": (user_agent or "")[:500],  # 截断超长 UA
            "detail": json.dumps(detail, ensure_ascii=False) if detail else None,
        }
        await self.audit_repo.create(db, entry)

    async def list_recent(self, db: Any, limit: int = 50) -> Any:
        """获取最近的审计日志记录。

        Args:
            db: aiosqlite 连接。
            limit: 最大返回条数，默认 50。

        Returns:
            审计日志记录列表。
        """
        return await self.audit_repo.list_recent(db, limit)

    async def list_by_user(self, db: Any, user: str, limit: int = 50) -> Any:
        """获取指定用户的审计日志记录。

        Args:
            db: aiosqlite 连接。
            user: 用户名。
            limit: 最大返回条数，默认 50。

        Returns:
            审计日志记录列表。
        """
        return await self.audit_repo.list_by_user(db, user, limit)
