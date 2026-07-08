"""
用户/角色仓库（T05）
管理用户、角色、用户-角色关联的数据库操作。
"""
from typing import Any


class UserRepository:
    """用户与角色的数据访问层。"""

    async def get_by_username(self, db: Any, username: str) -> dict[str, Any] | None:
        """按用户名查询用户。"""
        result = await db.execute_fetchone(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        return result  # type: ignore[no-any-return]

    async def get_by_id(self, db: Any, user_id: int) -> dict[str, Any] | None:
        """按用户 ID 查询用户。"""
        result = await db.execute_fetchone(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        return result  # type: ignore[no-any-return]

    async def create(
        self, db: Any, username: str, password_hash: str, email: str | None = None,
    ) -> int:
        """创建用户，返回新用户 ID。"""
        cursor = await db.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[no-any-return]

    async def get_user_role_ids(self, db: Any, user_id: int) -> list[str]:
        """获取用户的角色 ID 列表。"""
        rows = await db.execute_fetchall(
            "SELECT role_id FROM user_roles WHERE user_id = ?", (user_id,)
        )
        return [r["role_id"] for r in rows] if rows else []

    async def assign_role(self, db: Any, user_id: int, role_id: str) -> None:
        """为用户分配角色。"""
        await db.execute(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, role_id),
        )
        await db.commit()

    async def list_users(self, db: Any) -> list[dict[str, Any]]:
        """列出所有用户（不含密码哈希）。"""
        result = await db.execute_fetchall(
            "SELECT id, username, email, is_active, created_at, updated_at FROM users ORDER BY id"
        )
        return result  # type: ignore[no-any-return]
