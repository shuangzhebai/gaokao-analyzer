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

from config import VERSION
from deps import get_auto_scraper
from errors import global_exception_handler, http_exception_handler
from lifespan import create_lifespan
# 导入教育站点适配器（导入即触发 AdapterRegistry.register，scraper 构造时可见）
import edu_source_adapters  # noqa: F401 — 注册 xueke_wang / zujuan_wang 适配器

from models import get_db
from routes import analysis, audit, dedup, official_docs, papers, scrape, search

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
# 默认宽松兼容单机开发，生产环境通过环境变量 CORS_ORIGINS 限制
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理器（R-2：全局异常仅返回通用错误，不泄露内部路径/SQL）
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)


# ============ 鉴权中间件 ============

API_KEY = os.environ.get("API_KEY", "")
EXEMPT_PATHS = {"/", "/api/health"}

class AuthMiddleware(BaseHTTPMiddleware):
    """可选的 API Key 鉴权中间件。

    如果设置了环境变量 API_KEY，则所有 POST/DELETE/PUT 端点
    （除白名单路径外）需要 Authorization: Bearer <API_KEY> header。
    未设置 API_KEY 时，鉴权跳过（兼容单机使用）。
    """

    async def dispatch(self, request: Request, call_next):
        if API_KEY:
            if request.method in ("POST", "DELETE", "PUT") and request.url.path not in EXEMPT_PATHS:
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or auth[len("Bearer "):] != API_KEY:
                    return HTMLResponse(
                        status_code=401,
                        content="<h1>401 Unauthorized</h1><p>缺少或无效的 API Key</p>",
                    )
        response = await call_next(request)
        return response

app.add_middleware(AuthMiddleware)


# ============ 安全响应头 ============
# 在 CORS / Auth 之后注入 HSTS、X-Content-Type-Options、X-Frame-Options、
# Referrer-Policy 等安全头。不改变既有 CORS / Auth 中间件顺序与逻辑。

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """为所有 HTTP 响应追加安全响应头。"""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ============ API 速率限制（slowapi，全局默认 + 优雅降级） ============
# 采用全局 default_limits（200/min）即满足「API 速率限制」，不装饰各路由（避免改路由签名）。
if _HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


# ============ 页面路由 ============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 前端已在 lifespan 启动时读入内存（B-4），避免请求期同步 open() 阻塞事件循环
    return HTMLResponse(request.app.state.index_html)


# ============ 健康检查 ============

@app.get("/api/health")
async def health_check(db=Depends(get_db), auto_scraper=Depends(get_auto_scraper)):
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
