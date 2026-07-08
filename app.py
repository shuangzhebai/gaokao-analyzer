from typing import Any, Callable
"""
高考模拟卷智能分析系统 v5.1 - Web API 装配
v5.1: 路由拆分(routes/*)、lifespan 改造(@asynccontextmanager)、异常安全(R-2)、
      依赖注入(T04)、版本化迁移(T01)、统一版本号(Q-8)、前端内存缓存(B-4)
本文件只负责：创建 FastAPI 实例、注册 lifespan/异常处理器、装配路由、提供页面与健康检查。
"""
import logging
import os
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

from starlette.responses import Response

from config import VERSION
from deps import get_auto_scraper, get_audit_service, repo_user
from errors import global_exception_handler, http_exception_handler
from lifespan import create_lifespan

# P1-02: 导入 celery_app 即触发 Celery 初始化
import celery_app  # noqa: F401
from services.auth_service import AuthService
# 导入教育站点适配器（导入即触发 AdapterRegistry.register，scraper 构造时可见）
import edu_source_adapters  # noqa: F401 — 注册 xueke_wang / zujuan_wang 适配器

from models import get_db
from routes import analysis, audit, auth, dedup, official_docs, papers, scrape, search, tasks

# API 速率限制（slowapi）：若运行环境未安装 slowapi，则优雅降级（不启用限速）。
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    _HAS_SLOWAPI = True
except ImportError:  # pragma: no cover - 本地 venv 未装时优雅降级
    _HAS_SLOWAPI = False

logger = logging.getLogger("gaokao")

app = FastAPI(
    title="高考模拟卷智能分析系统",
    version=VERSION,
    lifespan=create_lifespan(),
)

# CORS 中间件（S-5：API 独立部署时跨域受限）
# T05: 从 CORS_ORIGINS 环境变量读取严格白名单，逗号分隔；未设置时回退通配符
cors_origins_env = os.environ.get("CORS_ORIGINS", "")
if cors_origins_env:
    origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    origins = ["*"]
    logger.warning("CORS_ORIGINS 未设置，使用通配符 '*' — 生产环境请设置严格白名单")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理器（R-2：全局异常仅返回通用错误，不泄露内部路径/SQL）
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]


# ============ 鉴权中间件 ============

API_KEY = os.environ.get("API_KEY", "")
# T05: 扩展豁免路径，包含 v1 路径 + auth 注册/登录
EXEMPT_PATHS = {
    "/", "/api/health", "/api/v1/health",
    "/api/auth/register", "/api/v1/auth/register",
    "/api/auth/login", "/api/v1/auth/login",
}

# JWT 鉴权服务实例（惰性初始化，供中间件使用）
_auth_service_instance: AuthService | None = None


def _get_auth_service() -> AuthService:
    """获取 AuthService 实例（线程安全的惰性初始化）。"""
    global _auth_service_instance
    if _auth_service_instance is None:
        _auth_service_instance = AuthService(user_repo=repo_user)
    return _auth_service_instance


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT + API Key 双重鉴权中间件（T05）。

    1. 优先尝试 JWT 令牌验证（Authorization: Bearer <JWT>）
    2. JWT 失败时回退 API Key 验证（兼容旧客户端）
    3. 未设置 API_KEY 且无 JWT 时，跳过鉴权（兼容单机使用）
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        # 豁免路径不鉴权
        if request.url.path in EXEMPT_PATHS:
            request.state.user = None
            return await call_next(request)

        auth = request.headers.get("Authorization", "")

        if auth.startswith("Bearer "):
            token = auth[len("Bearer "):]
            # 尝试 JWT 验证
            auth_service = _get_auth_service()
            try:
                payload = auth_service.verify_token(token)
                request.state.user = payload
                return await call_next(request)
            except ValueError:
                # JWT 验证失败，回退 API Key 验证
                pass

            # API Key 验证
            if API_KEY and token == API_KEY:
                request.state.user = {
                    "sub": 0, "role": "admin", "username": "api-key-user",
                }
                return await call_next(request)

            # 既不是有效 JWT，也不是有效 API Key
            return HTMLResponse(
                status_code=401,
                content="<h1>401 Unauthorized</h1><p>无效的认证令牌</p>",
            )

        # 无 Bearer token
        if API_KEY:
            # 检查是否需要鉴权（POST/PUT/DELETE）
            if request.method in ("POST", "DELETE", "PUT"):
                return HTMLResponse(
                    status_code=401,
                    content="<h1>401 Unauthorized</h1><p>缺少 Authorization 头</p>",
                )

        request.state.user = None
        response = await call_next(request)
        return response

app.add_middleware(AuthMiddleware)


# ============ 安全响应头 ============
# 在 CORS / Auth 之后注入 HSTS、X-Content-Type-Options、X-Frame-Options、
# Referrer-Policy 等安全头。不改变既有 CORS / Auth 中间件顺序与逻辑。

@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Any:
    """为所有 HTTP 响应追加安全响应头。"""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ============ 操作审计日志中间件 ============
# 审计 POST/PUT/DELETE 请求，自动记录操作者、资源、IP、UA 到 audit_log 表。
# 审计失败绝不阻塞用户请求——仅打印警告日志。
# 放在安全头之后、路由/限速之前，确保所有写操作均被记录。

@app.middleware("http")
async def audit_log_middleware(request: Request, call_next: Any) -> Any:
    """审计 POST/PUT/DELETE 请求，不阻塞正常响应。"""
    if request.method in ("POST", "PUT", "DELETE"):
        skip_paths = ['/api/health', '/api/v1/health', '/api/docs', '/api/openapi.json', '/api/auth', '/api/v1/auth']
        if not any(p in request.url.path for p in skip_paths):
            response = await call_next(request)
            try:
                audit_service = await get_audit_service(request)
                import aiosqlite
                from config import DB_PATH
                db = await aiosqlite.connect(DB_PATH)
                db.row_factory = aiosqlite.Row
                try:
                    # 提取当前用户（JWT 上线前回退 anonymous，T05 后自动完善）
                    user = "anonymous"
                    if hasattr(request.state, 'user') and request.state.user:
                        user = request.state.user.get('username', 'anonymous')

                    # 从路径推断资源类型与资源 ID
                    path_parts = request.url.path.strip('/').split('/')
                    resource_type = path_parts[-2] if len(path_parts) >= 2 else 'unknown'
                    resource_id = path_parts[-1] if path_parts[-1].isdigit() else None

                    await audit_service.log(
                        db=db,
                        user=user,
                        action=request.method,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                    )
                    await db.commit()
                finally:
                    await db.close()
            except Exception as e:  # noqa: BLE001
                # 审计失败绝不阻塞请求——仅记日志警告
                print(f"[audit] log failed: {e}")
            return response
    return await call_next(request)


# ============ API 速率限制（slowapi，全局默认 + 优雅降级） ============
# 采用全局 default_limits（200/min）即满足「API 速率限制」，不装饰各路由（避免改路由签名）。
if _HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)


# ============ 页面路由 ============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Any:
    # 前端已在 lifespan 启动时读入内存（B-4），避免请求期同步 open() 阻塞事件循环
    return HTMLResponse(request.app.state.index_html)


# P1-04: 服务端 locale 文件（允许前端 i18n.js 通过 GET 加载）
import json as json_mod
import os


@app.get("/locales/{lang}.json")
async def get_locale(lang: str) -> dict[str, str]:
    locale_path = os.path.join(os.path.dirname(__file__), "locales", f"{lang}.json")
    try:
        with open(locale_path, "r", encoding="utf-8") as f:
            return json_mod.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


# ============ 健康检查 ============

@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check(db: Any = Depends(get_db), auto_scraper: Any = Depends(get_auto_scraper)) -> dict[str, Any]:
    try:
        count = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
        docs_count = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM official_docs")
        return {
            "status": "ok",
            "papers_count": count["cnt"] if count else 0,
            "official_docs_count": docs_count["cnt"] if docs_count else 0,
            "version": VERSION,
            "features": ["fts5_search", "deepseek_dedup", "source_tracking",
                         "region_validator", "auto_scraper", "cross_verify",
                         "official_docs", "calibrated_simulation", "auth_audit"],
            "auto_scraper_status": auto_scraper.get_status() if auto_scraper else None,
        }
    except Exception as e:  # noqa: BLE001
        logger.error("健康检查失败: %s", e)
        return {"status": "error", "message": "服务暂不可用"}


# ============ 装配路由 ============

app.include_router(papers.router)
app.include_router(search.router)
app.include_router(dedup.router)
app.include_router(scrape.router)
app.include_router(audit.router)
app.include_router(official_docs.router)
app.include_router(analysis.router)
app.include_router(auth.router)
app.include_router(tasks.router)
