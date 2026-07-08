"""
认证路由（T05）
注册、登录端点。
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

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
    """用户登录，返回 JWT token。"""
    try:
        return await auth_service.login(db, username, password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
