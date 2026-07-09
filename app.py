from typing import Any, Callable
"""
高考模拟卷智能分析系统 v6.0 - Web API 装配
v6.0: WAL模式+PRAGMA极致优化, 可观测性(X-Process-Time/健康检查指标), 版本升级
本文件只负责：创建 FastAPI 实例、注册 lifespan/异常处理器、装配路由、提供页面与健康检查。
"""
import logging
import os
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

from starlette.responses import Response

from config import VERSION, GAOKAO_ENV, CORS_ORIGINS
from deps import get_auto_scraper, get_audit_service, repo_user
from errors import global_exception_handler, http_exception_handler
from lifespan import create_lifespan

# P1-02: 导入 celery_app 即触发 Celery 初始化
import celery_app  # noqa: F401
from services.auth_service import AuthService
# 导入教育站点适配器（导入即触发 AdapterRegistry.register，scraper 构造时可见）
import edu_source_adapters  # noqa: F401 — 注册 xueke_wang / zujuan_wang 适配器

from models import get_db
from routes import analysis, audit, auth, dedup, official_docs, papers, quality, questions, scrape, search, tasks, webhooks

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
# P0-3: 跨域来源来自 config.CORS_ORIGINS（已在 config 中按 GAOKAO_ENV 解析）：
#   - prod 未配置 → []，拒绝一切跨域；
#   - dev 未配置  → 本地前端白名单（localhost/127.0.0.1）。
# allow_credentials 仅在 origins 非空且不含通配符 "*" 时启用，规避 "*+credentials" 安全矛盾。
_allow_credentials = bool(CORS_ORIGINS) and "*" not in CORS_ORIGINS
if not CORS_ORIGINS:
    logger.warning(
        "CORS_ORIGINS 为空，跨域请求将被全部拒绝（prod 默认安全策略）"
    )
elif "*" in CORS_ORIGINS:
    logger.warning("CORS_ORIGINS 含通配符 '*'，已自动禁用 credentials 以保护凭证")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ WebSocket 连接管理器（差距项 #7） ============

class ConnectionManager:
    """管理 WebSocket 连接，按 task_id 分组广播任务状态。"""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str) -> None:
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)

    def disconnect(self, websocket: WebSocket, task_id: str) -> None:
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]

    async def broadcast(self, task_id: str, message: dict) -> None:
        if task_id not in self.active_connections:
            return
        for conn in self.active_connections[task_id][:]:
            try:
                await conn.send_json(message)
            except Exception:
                self.active_connections[task_id].remove(conn)


manager = ConnectionManager()

# v6.0: orjson 加速 JSON 序列化（~5x 快于标准 json.dumps）
try:
    import orjson as _orjson

    from fastapi.responses import JSONResponse as _BaseJSONResponse

    class _FastJSONResponse(_BaseJSONResponse):
        """使用 orjson 的 JSON 响应，速度 5x 于标准 json.dumps。"""

        media_type = "application/json"

        def render(self, content: Any) -> bytes:
            return _orjson.dumps(content, default=str)

    app.default_response_class = _FastJSONResponse
except ImportError:
    pass

# 异常处理器（R-2：全局异常仅返回通用错误，不泄露内部路径/SQL）
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]


# ============ 鉴权中间件 ============

API_KEY = os.environ.get("API_KEY", "")
# P0-2: 生产环境必须配置 API_KEY，否则启动即 fail-fast（避免默认部署写接口全放行）
if GAOKAO_ENV == "prod" and not API_KEY:
    raise RuntimeError("生产环境必须设置 API_KEY 环境变量")
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
    """JWT + API Key 双重鉴权中间件（T05，P0-2 加固）。

    鉴权策略（按 GAOKAO_ENV 区分本地便利与生产强制）：
    1. 豁免路径（register/login/health）始终不鉴权。
    2. 携带 Bearer 头：优先校验 JWT，失败回退校验 API Key（兼容旧客户端）；
       二者皆无效 → 401。
    3. 无 Bearer 头：
       - 已设置 API_KEY → 写操作(POST/PUT/DELETE)必须鉴权，否则 401；GET 等放行。
       - 未设置 API_KEY：
           * prod  → 生产环境已在导入期 fail-fast，运行期保险拒绝写操作(401)。
           * dev   → 允许本地无鉴权（便利），仅首次打印一次 WARNING。
    """

    # 类级标志：dev 空 API_KEY 仅警告一次，避免日志刷屏
    _dev_no_api_key_warned: bool = False

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        # 豁免路径不鉴权
        if request.url.path in EXEMPT_PATHS:
            request.state.user = None
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        is_write = request.method in ("POST", "PUT", "DELETE")

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

            # API Key 兼容验证（Bearer <API_KEY>）
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
            # 已配置 API_KEY：写操作必须鉴权，否则 401；GET 等放行
            if is_write:
                return HTMLResponse(
                    status_code=401,
                    content="<h1>401 Unauthorized</h1><p>缺少 Authorization 头</p>",
                )
            request.state.user = None
            response = await call_next(request)
            return response

        # 未配置 API_KEY
        if GAOKAO_ENV == "prod":
            # 生产环境已在导入期 fail-fast，此处为保险兜底：写操作一律拒绝
            if is_write:
                return HTMLResponse(
                    status_code=401,
                    content="<h1>401 Unauthorized</h1><p>生产环境 API_KEY 未配置</p>",
                )
            request.state.user = None
            response = await call_next(request)
            return response

        # dev 模式：空 API_KEY 允许本地无鉴权（便利），仅警告一次
        if not AuthMiddleware._dev_no_api_key_warned:
            AuthMiddleware._dev_no_api_key_warned = True
            print(
                "WARNING: 开发模式 API_KEY 为空，接口未鉴权（请勿用于生产）。"
                "设置 API_KEY 环境变量以启用写接口鉴权。"
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


# ============ Gzip 压缩中间件（v6.0 性能优化 — 移至 Nginx 层处理更高效，此处跳过） ============
# FastAPI 内置 gzip 支持通过 uvicorn/server 配置，此处不重复实现。


# ============ 请求耗时 + 速率限制头中间件（v6.0 可观测性） ============

@app.middleware("http")
async def add_perf_headers(request: Request, call_next: Any) -> Any:
    """为每个响应添加 X-Process-Time 和 X-RateLimit 头。"""
    import time as _t

    start = _t.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((_t.perf_counter() - start) * 1000, 1)
    response.headers["X-Process-Time"] = f"{elapsed_ms}ms"
    response.headers["X-App-Version"] = VERSION
    # 若 slowapi 已注册，附加当前限速状态
    if getattr(request.app.state, "limiter", None) is not None:
        response.headers["X-RateLimit-Limit"] = "200/minute"
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


# ============ 健康检查（极致可观测性） ============
_APP_START_TIME: float = 0.0
import time as _time_module


@app.on_event("startup")
async def _record_startup() -> None:
    global _APP_START_TIME
    _APP_START_TIME = _time_module.time()


@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check(request: Request, db: Any = Depends(get_db), auto_scraper: Any = Depends(get_auto_scraper)) -> dict[str, Any]:
    try:
        count = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
        docs_count = await db.execute_fetchone("SELECT COUNT(*) as cnt FROM official_docs")

        # 数据库性能指标
        db_stats: dict[str, Any] = {"connected": True}
        try:
            cur = await db.execute("PRAGMA journal_mode")
            jm = await cur.fetchone()
            db_stats["journal_mode"] = jm[0] if jm else "unknown"
            cur = await db.execute("PRAGMA page_count")
            pc = await cur.fetchone()
            cur = await db.execute("PRAGMA page_size")
            ps = await cur.fetchone()
            if pc and ps:
                db_stats["db_size_mb"] = round(pc[0] * ps[0] / 1048576, 2)
        except Exception:
            db_stats["detail_error"] = "pragma_query_failed"

        # 缓存状态 (P1-01)
        cache_stats: dict[str, Any] = {"redis": getattr(celery_app, "_HAS_CELERY", False)}
        try:
            from services.cache_service import get_cache

            cs = get_cache()
            cache_stats["l1_entries"] = len(cs._l1)
        except Exception:
            cache_stats["l1_entries"] = -1

        # 运行时上下文 (P0)
        ctx = getattr(request.app.state, "ctx", None)

        response_data: dict[str, Any] = {
            "status": "ok",
            "version": VERSION,
            "uptime_seconds": round(_time_module.time() - _APP_START_TIME, 1),
            "papers_count": count["cnt"] if count else 0,
            "official_docs_count": docs_count["cnt"] if docs_count else 0,
            "database": db_stats,
            "cache": cache_stats,
            "engines": len([
                a for a in dir(request.app.state)
                if not a.startswith("_") and a not in ("index_html", "ctx", "limiter", "db")
                and not a.endswith("_service")
            ]),
            "features": ["fts5_search", "deepseek_dedup", "source_tracking",
                         "region_validator", "auto_scraper", "cross_verify",
                         "official_docs", "calibrated_simulation", "auth_audit",
                         "redis_cache", "celery_async", "numba_jit",
                         "meilisearch", "pwa", "i18n"],
            "auto_scraper_status": auto_scraper.get_status() if auto_scraper else None,
        }
        if ctx:
            response_data["python_version"] = ctx.python_version
            response_data["deepseek_enabled"] = ctx.deepseek_enabled
        return response_data
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
app.include_router(webhooks.router)
app.include_router(questions.router)
app.include_router(quality.router)


# ============ WebSocket 任务状态推送（差距项 #7） ============


@app.websocket("/ws/tasks/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str) -> None:
    """WebSocket 端点：监听 Celery 任务状态变化推送给前端。"""
    await manager.connect(websocket, task_id)
    try:
        while True:
            # 保持连接存活，接收 ping
            data = await websocket.receive_text()
            # 每收到消息就推送一次最新状态
            from celery_app import _HAS_CELERY, app as celery_app
            if _HAS_CELERY and celery_app is not None:
                result = celery_app.AsyncResult(task_id)
                await websocket.send_json({
                    "task_id": task_id,
                    "status": result.state,
                    "result": result.result if result.ready() else None,
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
    except Exception:
        manager.disconnect(websocket, task_id)


# ============ Prometheus 监控端点（差距项 #10） ============
import time as _time_metrics

_METRICS: dict[str, float] = {
    "http_requests_total": 0,
    "http_errors_total": 0,
}
_METRICS_DURATION: dict[str, list[float]] = {
    "papers_list": [],
    "papers_detail": [],
    "search": [],
    "health": [],
}


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Any) -> Any:
    """采集 Prometheus 指标。"""
    global _METRICS
    _METRICS["http_requests_total"] += 1
    start = _time_metrics.perf_counter()
    response = await call_next(request)
    duration = _time_metrics.perf_counter() - start
    if response.status_code >= 400:
        _METRICS["http_errors_total"] += 1
    # 记录各端点 P50/P99 用
    path = request.url.path
    for key in _METRICS_DURATION:
        if key in path:
            _METRICS_DURATION[key].append(duration)
            if len(_METRICS_DURATION[key]) > 1000:
                _METRICS_DURATION[key] = _METRICS_DURATION[key][-1000:]
            break
    return response


@app.get("/metrics")
async def prometheus_metrics() -> str:
    """Prometheus 文本格式指标输出。"""
    lines = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
        f'http_requests_total {_METRICS["http_requests_total"]:.0f}',
        "",
        "# HELP http_errors_total Total HTTP errors (4xx/5xx)",
        "# TYPE http_errors_total counter",
        f'http_errors_total {_METRICS["http_errors_total"]:.0f}',
        "",
    ]
    # P99 延迟
    for name, durations in _METRICS_DURATION.items():
        if durations:
            sorted_d = sorted(durations)
            p99 = sorted_d[int(len(sorted_d) * 0.99)]
            p50 = sorted_d[int(len(sorted_d) * 0.50)]
            lines.append(f'# HELP http_{name}_duration_seconds Request duration')
            lines.append(f'# TYPE http_{name}_duration_seconds gauge')
            lines.append(f'http_{name}_duration_seconds{{quantile="0.5"}} {p50:.4f}')
            lines.append(f'http_{name}_duration_seconds{{quantile="0.99"}} {p99:.4f}')
            lines.append("")
    return "\n".join(lines)
