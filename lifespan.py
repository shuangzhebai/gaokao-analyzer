"""
应用生命周期管理（T03）
使用 @asynccontextmanager 替代已弃用的 @on_event("startup"/"shutdown")。
在启动时初始化所有引擎单例并存入 app.state（供依赖注入使用），
并在启动时将前端 index.html 读入内存缓存（避免运行时同步读磁盘阻塞事件循环，B-4）。
v5.2: 引擎初始化并行化（P-2），使用 asyncio.gather 加速冷启动。
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from config import DATA_DIR, get_deepseek_key
from models import init_db, optimize_fts, seed_data
from scraper import ScraperManager
from parser import PaperParser
from analyzer import IRTModel, KnowledgeMapper, QualityAnalyzer
from simulator import MonteCarloSimulator, FittingAnalyzer
from curriculum import CurriculumAnalyzer
from quality import QualityScorer
from search import SearchEngine
from dedup import DedupEngine
from auto_scraper import AutoScraper
from official_docs import OfficialDocsLibrary
from paper_analysis import PaperAnalyzer
from app_context import build_app_context

logger = logging.getLogger("gaokao")


async def _init_engine(app: FastAPI, attr_name: str, factory: Any, *args: Any, **kwargs: Any) -> Any:
    """同步构造型引擎初始化，异常时仅警告不中断启动流程。"""
    try:
        instance = factory(*args, **kwargs)
        setattr(app.state, attr_name, instance)
        logger.debug("引擎 %s 初始化完成", attr_name)
        return instance
    except Exception as e:  # noqa: BLE001
        logger.warning("引擎 %s 初始化失败: %s", attr_name, e)
        return None


async def _init_async(app: FastAPI, coro: Any, label: str = "unknown") -> None:
    """异步型引擎初始化（如 await .start()），异常时仅警告。"""
    try:
        await coro
        logger.debug("引擎 %s 异步初始化完成", label)
    except Exception as e:  # noqa: BLE001
        logger.warning("引擎 %s 异步初始化失败: %s", label, e)


def create_lifespan() -> Any:
    """返回一个 FastAPI lifespan 上下文管理器。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # ---------- 启动 ----------
        os.makedirs(DATA_DIR, exist_ok=True)
        await init_db()       # 含版本化迁移（T01），不删库
        await seed_data()
        await optimize_fts()  # P-6：启动时优化 FTS5 索引碎片

        # ======== 引擎初始化并行化（P-2） ========
        # 阶段一：所有同步构造引擎并行初始化
        await asyncio.gather(
            _init_engine(app, "scraper_manager", ScraperManager),
            _init_engine(app, "irt_model", IRTModel),
            _init_engine(app, "kp_mapper", KnowledgeMapper),
            _init_engine(app, "quality_analyzer", QualityAnalyzer),
            _init_engine(app, "simulator", MonteCarloSimulator),
            _init_engine(app, "fitting_analyzer", FittingAnalyzer),
            _init_engine(app, "paper_parser", PaperParser),
            _init_engine(app, "curriculum_analyzer", CurriculumAnalyzer),
            _init_engine(app, "quality_scorer", QualityScorer),
            _init_engine(app, "search_engine", SearchEngine),
            _init_engine(app, "dedup_engine", DedupEngine,
                         deepseek_api_key=get_deepseek_key() or None),
            _init_engine(app, "auto_scraper", AutoScraper,
                         deepseek_api_key=get_deepseek_key() or ""),
            _init_engine(app, "official_docs", OfficialDocsLibrary),
            _init_engine(app, "paper_analyzer", PaperAnalyzer),
        )

        # 阶段二：异步启动操作并行执行
        await asyncio.gather(
            _init_async(app, app.state.auto_scraper.start(), "auto_scraper.start"),
            _init_async(app, app.state.official_docs.seed_official_docs(),
                        "official_docs.seed_official_docs"),
        )

        # 预读前端页面到内存（B-4：避免请求期同步 open() 阻塞事件循环）
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                app.state.index_html = f.read()
        except FileNotFoundError:
            logger.warning("static/index.html 未找到，返回占位页")
            app.state.index_html = "<html><body>前端文件缺失</body></html>"

        logger.info("gaokao-analyzer startup complete - engines ready, index cached")

        # 运行时上下文集中化（批次二：T-C2）：构建不可变快照存入 app.state.ctx，
        # 供依赖注入 get_app_context 与路由统一读取。
        app.state.ctx = build_app_context(app)

        # P1-01: Redis 双级缓存初始化（无 Redis 时自动降级）
        from services.cache_service import init_cache

        await init_cache()

        # P2-04: Meilisearch 索引初始化（无 Meilisearch 时自动降级）
        try:
            from search import MeiliSearchBackend

            await MeiliSearchBackend.ensure_indexes()
        except Exception:
            pass

        yield

        # ---------- 关闭 ----------
        if getattr(app.state, "scraper_manager", None):
            await app.state.scraper_manager.close()
        if getattr(app.state, "auto_scraper", None):
            await app.state.auto_scraper.stop()
        # P1-01: 关闭 Redis 连接
        from services.cache_service import _close_redis

        await _close_redis()
        logger.info("gaokao-analyzer shutdown complete")

    return lifespan
