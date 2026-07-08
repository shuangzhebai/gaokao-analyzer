"""
认证服务（T05）
JWT 令牌签发/验证、密码哈希、用户注册/登录。
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from repositories.user_repo import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_PRIORITY: dict[str, int] = {
    "admin": 0,
    "teacher": 1,
    "viewer": 2,
}


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
        """签发 JWT 令牌，含 sub(用户ID)、username、role、tenant_id 及过期时间。"""
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "tenant_id": tenant_id,
            "exp": expire,
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)  # type: ignore[no-any-return]

    def verify_token(self, token: str) -> dict[str, Any]:
        """验证 JWT 令牌，返回 payload 或抛出异常。"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload  # type: ignore[no-any-return]
        except JWTError:
            raise ValueError("无效或已过期的令牌")

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
        return {
            "token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user.get("email"),
                "role": role,
                "tenant_id": user.get("tenant_id", "default"),
            },
        }
