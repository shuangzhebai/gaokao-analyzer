"""
应用生命周期管理（T03）
使用 @asynccontextmanager 替代已弃用的 @on_event("startup"/"shutdown")。
在启动时初始化所有引擎单例并存入 app.state（供依赖注入使用），
并在启动时将前端 index.html 读入内存缓存（避免运行时同步读磁盘阻塞事件循环，B-4）。
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import DATA_DIR, get_deepseek_key
from models import init_db, seed_data
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

logger = logging.getLogger("gaokao")


def create_lifespan():
    """返回一个 FastAPI lifespan 上下文管理器。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ---------- 启动 ----------
        os.makedirs(DATA_DIR, exist_ok=True)
        await init_db()       # 含版本化迁移（T01），不删库
        await seed_data()

        # 初始化引擎单例到 app.state（依赖注入源，T04）
        app.state.scraper_manager = ScraperManager()
        app.state.irt_model = IRTModel()
        app.state.kp_mapper = KnowledgeMapper()
        app.state.quality_analyzer = QualityAnalyzer()
        app.state.simulator = MonteCarloSimulator()
        app.state.fitting_analyzer = FittingAnalyzer()
        app.state.paper_parser = PaperParser()
        app.state.curriculum_analyzer = CurriculumAnalyzer()
        app.state.quality_scorer = QualityScorer()
        app.state.search_engine = SearchEngine()
        app.state.dedup_engine = DedupEngine(deepseek_api_key=get_deepseek_key() or None)
        app.state.auto_scraper = AutoScraper(deepseek_api_key=get_deepseek_key() or "")
        await app.state.auto_scraper.start()
        app.state.official_docs = OfficialDocsLibrary()
        await app.state.official_docs.seed_official_docs()
        # 阶段二：试卷质量分析引擎（供 /api/papers/.../analyze 复用，含缓存）
        app.state.paper_analyzer = PaperAnalyzer()

        # 预读前端页面到内存（B-4：避免请求期同步 open() 阻塞事件循环）
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                app.state.index_html = f.read()
        except FileNotFoundError:
            logger.warning("static/index.html 未找到，返回占位页")
            app.state.index_html = "<html><body>前端文件缺失</body></html>"

        logger.info("gaokao-analyzer startup complete - engines ready, index cached")

        yield

        # ---------- 关闭 ----------
        if getattr(app.state, "scraper_manager", None):
            await app.state.scraper_manager.close()
        if getattr(app.state, "auto_scraper", None):
            await app.state.auto_scraper.stop()
        logger.info("gaokao-analyzer shutdown complete")

    return lifespan
