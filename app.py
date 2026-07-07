"""
高考模拟卷智能分析系统 v5.1 - Web API 装配
v5.1: 路由拆分(routes/*)、lifespan 改造(@asynccontextmanager)、异常安全(R-2)、
      依赖注入(T04)、版本化迁移(T01)、统一版本号(Q-8)、前端内存缓存(B-4)
本文件只负责：创建 FastAPI 实例、注册 lifespan/异常处理器、装配路由、提供页面与健康检查。
"""
import logging
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from config import VERSION
from deps import get_auto_scraper
from errors import global_exception_handler, http_exception_handler
from lifespan import create_lifespan
from models import get_db
from routes import analysis, audit, dedup, official_docs, papers, scrape, search

logger = logging.getLogger("gaokao")

app = FastAPI(
    title="高考模拟卷智能分析系统",
    version=VERSION,
    lifespan=create_lifespan(),
)

# 异常处理器（R-2：全局异常仅返回通用错误，不泄露内部路径/SQL）
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)


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
        return {"status": "error", "message": str(e)}


# ============ 装配路由 ============

app.include_router(papers.router)
app.include_router(search.router)
app.include_router(dedup.router)
app.include_router(scrape.router)
app.include_router(audit.router)
app.include_router(official_docs.router)
app.include_router(analysis.router)
