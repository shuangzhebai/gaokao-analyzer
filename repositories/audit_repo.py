"""
操作审计日志 DAO：封装 audit_log 表的所有 SQL 操作（aiosqlite，不引入 ORM）。
与 verification_audit（试卷真实性审核）完全独立。
"""


from typing import Any


class AuditRepository:
    """操作审计日志数据访问对象"""

    async def create(self, db: Any, entry: dict[str, Any]) -> Any:
        """插入一条审计日志记录，返回自增 id。

        Args:
            db: aiosqlite 连接（含 execute_fetchone 等包装方法）。
            entry: 包含 user, action, resource_type, resource_id,
                   ip_address, user_agent, detail 的字典。

        Returns:
            新插入记录的 id（lastrowid）。
        """
        cursor = await db.execute(
            """INSERT INTO audit_log
               (user, action, resource_type, resource_id, ip_address, user_agent, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.get("user", "anonymous"),
                entry.get("action", ""),
                entry.get("resource_type", ""),
                entry.get("resource_id"),
                entry.get("ip_address", ""),
                entry.get("user_agent", ""),
                entry.get("detail"),
            ),
        )
        return cursor.lastrowid

    async def list_recent(self, db: Any, limit: int = 50) -> Any:
        """获取最近的审计日志记录，按时间倒序排列。

        Args:
            db: aiosqlite 连接。
            limit: 最大返回条数，默认 50。

        Returns:
            审计日志记录列表。
        """
        return await db.execute_fetchall(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    async def list_by_user(self, db: Any, user: str, limit: int = 50) -> Any:
        """获取指定用户的审计日志记录，按时间倒序排列。

        Args:
            db: aiosqlite 连接。
            user: 用户名。
            limit: 最大返回条数，默认 50。

        Returns:
            审计日志记录列表。
        """
        return await db.execute_fetchall(
            "SELECT * FROM audit_log WHERE user = ? ORDER BY created_at DESC LIMIT ?",
            (user, limit),
        )
