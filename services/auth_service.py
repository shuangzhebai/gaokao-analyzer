"""
认证服务（T05）
JWT 令牌签发/验证、密码哈希、用户注册/登录。
P2-4: 增加 refresh token / 吊销 / jti。
"""
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import (
    JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET,
    JWT_REFRESH_EXPIRE_DAYS, JWT_REFRESH_SECRET,
    TOKEN_BLACKLIST_ENABLED,
)
from repositories.user_repo import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_PRIORITY: dict[str, int] = {
    "admin": 0,
    "teacher": 1,
    "viewer": 2,
}

_USERNAME_MIN = 3
_USERNAME_MAX = 50
_PASSWORD_MIN = 6
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class AuthService:
    """认证服务：密码管理、JWT 令牌、注册/登录。"""

    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    def hash_password(self, password: str) -> str:
        """对明文密码进行 bcrypt 哈希。"""
        return pwd_context.hash(password)  # type: ignore[no-any-return]

    def verify_password(self, plain: str, hashed: str) -> bool:
        """验证明文密码与哈希匹配。"""
        return pwd_context.verify(plain, hashed)  # type: ignore[no-any-return]

    def create_token(self, user_id: int, username: str, role: str, tenant_id: str = "default") -> str:
        """签发 JWT 令牌，含 sub(用户ID)、username、role、tenant_id、jti 及过期时间。"""
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
        jti = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "tenant_id": tenant_id,
            "jti": jti,
            "type": "access",
            "exp": expire,
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)  # type: ignore[no-any-return]

    def create_refresh_token(self, user_id: int, username: str, role: str, tenant_id: str = "default") -> str:
        """签发 refresh JWT 令牌（更长有效期，独立 secret）。"""
        expire = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_EXPIRE_DAYS)
        jti = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "tenant_id": tenant_id,
            "jti": jti,
            "type": "refresh",
            "exp": expire,
        }
        return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)  # type: ignore[no-any-return]

    def verify_token(self, token: str) -> dict[str, Any]:
        """验证 JWT 令牌，返回 payload 或抛出异常。"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload  # type: ignore[no-any-return]
        except JWTError:
            raise ValueError("无效或已过期的令牌")

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """验证 refresh JWT 令牌，返回 payload 或抛出异常。"""
        try:
            payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
            return payload  # type: ignore[no-any-return]
        except JWTError:
            raise ValueError("无效或已过期的 refresh 令牌")

    async def is_token_blacklisted(self, db: Any, jti: str) -> bool:
        """检查 jti 是否在 token 黑名单中。"""
        if not TOKEN_BLACKLIST_ENABLED:
            return False
        try:
            row = await db.execute_fetchone(
                "SELECT 1 FROM token_blacklist WHERE jti = ?", (jti,)
            )
            return row is not None
        except Exception:  # noqa: BLE001 - 黑名单表可能尚不存在
            return False

    async def revoke_token(self, db: Any, jti: str, token_type: str, user_id: int, expires_at: str, tenant_id: str | None = None) -> None:
        """将 token 加入黑名单（吊销）。"""
        if not TOKEN_BLACKLIST_ENABLED:
            return
        try:
            await db.execute(
                """INSERT OR IGNORE INTO token_blacklist (jti, token_type, user_id, expires_at, tenant_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (jti, token_type, user_id, expires_at, tenant_id),
            )
            await db.commit()
        except Exception as e:  # noqa: BLE001
            # 黑名单插入失败不阻塞流程，仅记日志
            import logging
            logging.getLogger("gaokao").warning("token 吊销写入失败: %s", e)

    async def register(
        self,
        db: Any,
        username: str,
        password: str,
        email: str | None = None,
        role: str = "viewer",
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """注册新用户，返回用户信息。

        P2-02: 新增 tenant_id 参数，支持多租户隔离。

        Args:
            db: 数据库连接
            username: 用户名
            password: 明文密码
            email: 可选邮箱
            role: 初始角色（默认 viewer）
            tenant_id: 租户 ID（默认 "default"）

        Returns:
            包含 id, username, role, tenant_id 的用户信息字典

        Raises:
            ValueError: 用户名已存在或角色无效
        """
        # 校验输入
        username = username.strip()
        if len(username) < _USERNAME_MIN or len(username) > _USERNAME_MAX:
            raise ValueError(f"用户名长度需在 {_USERNAME_MIN}-{_USERNAME_MAX} 字符之间")
        if len(password) < _PASSWORD_MIN:
            raise ValueError(f"密码长度不能少于 {_PASSWORD_MIN} 个字符")
        if email and not _EMAIL_REGEX.match(email):
            raise ValueError("邮箱格式无效")

        # 校验角色
        if role not in ROLE_PRIORITY:
            raise ValueError(f"无效角色: {role}，可选: {', '.join(ROLE_PRIORITY)}")

        # 检查用户是否已存在
        existing = await self.user_repo.get_by_username(db, username)
        if existing:
            raise ValueError(f"用户名 '{username}' 已存在")

        password_hash = self.hash_password(password)
        user_id = await self.user_repo.create(db, username, password_hash, email)

        # 分配角色
        await self.user_repo.assign_role(db, user_id, role)

        return {"id": user_id, "username": username, "role": role, "tenant_id": tenant_id}

    async def login(self, db: Any, username: str, password: str) -> dict[str, Any]:
        """用户登录：验证凭据，返回 token 及用户信息。

        P2-02: 租户 ID 从用户记录读取。

        Args:
            db: 数据库连接
            username: 用户名
            password: 明文密码

        Returns:
            包含 token、token_type、user 的字典

        Raises:
            ValueError: 用户名不存在或密码错误
        """
        user = await self.user_repo.get_by_username(db, username)
        if not user:
            raise ValueError(f"用户 '{username}' 不存在")

        if user.get("is_active") == 0:
            raise ValueError("该用户已被停用")

        if not self.verify_password(password, user["password_hash"]):
            raise ValueError("密码错误")

        # 获取用户角色（取最高优先级角色）
        role_ids = await self.user_repo.get_user_role_ids(db, user["id"])
        role = "viewer"
        if role_ids:
            role = min(role_ids, key=lambda r: ROLE_PRIORITY.get(r, 99))

        token = self.create_token(user["id"], user["username"], role, user.get("tenant_id", "default"))
        refresh_token = self.create_refresh_token(user["id"], user["username"], role, user.get("tenant_id", "default"))
        return {
            "token": token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email"),
                "role": role,
                "tenant_id": user.get("tenant_id", "default"),
            },
        }
