"""
认证路由（T05）
注册、登录端点。
P2-4: 增加 refresh token / revoke 端点。
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Header

from deps import get_auth_service
from models import get_db
from services.auth_service import AuthService

router = APIRouter()


@router.post("/api/v1/auth/register")
@router.post("/api/auth/register", include_in_schema=False)
async def register(
    username: str,
    password: str,
    email: str | None = None,
    role: str = "viewer",
    db: Any = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """注册新用户。"""
    try:
        user = await auth_service.register(db, username, password, email, role)
        return {"ok": True, "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/auth/login")
@router.post("/api/auth/login", include_in_schema=False)
async def login(
    username: str,
    password: str,
    db: Any = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """用户登录，返回 JWT token 及 refresh_token。"""
    try:
        return await auth_service.login(db, username, password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ============ P2-4: JWT 刷新 / 吊销 ============


@router.post("/api/v1/auth/refresh")
@router.post("/api/auth/refresh", include_in_schema=False)
async def refresh_token(
    refresh_token: str,
    db: Any = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """使用 refresh_token 换取新的 access_token + refresh_token。"""
    try:
        payload = auth_service.verify_refresh_token(refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # 检查 refresh token 是否已被吊销
    jti = payload.get("jti", "")
    if jti:
        blacklisted = await auth_service.is_token_blacklisted(db, jti)
        if blacklisted:
            raise HTTPException(status_code=401, detail="refresh token 已被吊销")

    user_id = int(payload["sub"])
    username = payload.get("username", "")
    role = payload.get("role", "viewer")
    tenant_id = payload.get("tenant_id", "default")

    # 签发新令牌
    new_access_token = auth_service.create_token(user_id, username, role, tenant_id)
    new_refresh_token = auth_service.create_refresh_token(user_id, username, role, tenant_id)

    # 旧 refresh token 加入黑名单（轮换机制）
    expires_at = payload.get("exp")
    if expires_at and jti:
        from datetime import datetime, timezone
        exp_str = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        await auth_service.revoke_token(db, jti, "refresh", user_id, exp_str, tenant_id)

    return {
        "token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/api/v1/auth/revoke")
@router.post("/api/auth/revoke", include_in_schema=False)
async def revoke_token(
    authorization: str = Header(..., alias="Authorization"),
    db: Any = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    """吊销当前 access_token（将其 jti 加入黑名单）。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="无效的 Authorization 头")

    token = authorization[len("Bearer "):]
    try:
        payload = auth_service.verify_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    jti = payload.get("jti", "")
    if not jti:
        raise HTTPException(status_code=400, detail="令牌缺少 jti 字段")

    user_id = int(payload["sub"])
    tenant_id = payload.get("tenant_id")
    expires_at = payload.get("exp")
    from datetime import datetime, timezone
    exp_str = datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if expires_at else ""

    await auth_service.revoke_token(db, jti, "access", user_id, exp_str, tenant_id)
    return {"ok": True, "message": "令牌已吊销"}
