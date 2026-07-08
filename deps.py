"""
依赖注入（T03/T04）
从 app.state 获取在 lifespan 中初始化的引擎单例，以及数据库连接。
避免全局可变单例直接引用，提升可测试性与可维护性（Q-2）。

T01 扩展：新增 service 依赖注入函数，注册 PaperService / AnalysisService /
ScrapeService / FilterService 到 app.state（惰性初始化）。
"""
from fastapi import Request

from models import get_db
from app_context import AppContext

from repositories.paper_repo import PaperRepository
from repositories.question_repo import QuestionRepository
from repositories.analysis_repo import AnalysisRepository
from repositories.audit_repo import AuditRepository

from services.paper_service import PaperService
from services.analysis_service import AnalysisService
from services.scrape_service import ScrapeService
from services.filter_service import FilterService
from services.audit_service import AuditService

# ============ Repository 单例（无状态，可跨请求复用） ============
repo_paper = PaperRepository()
repo_question = QuestionRepository()
repo_analysis = AnalysisRepository()
repo_audit = AuditRepository()


# ============ Service 惰性初始化（防止 lifespan 之前被意外调用） ============

async def get_paper_service(request: Request) -> PaperService:
    if not hasattr(request.app.state, 'paper_service'):
        request.app.state.paper_service = PaperService(
            paper_repo=repo_paper,
            question_repo=repo_question,
            analysis_repo=repo_analysis,
        )
    return request.app.state.paper_service


async def get_analysis_service(request: Request) -> AnalysisService:
    if not hasattr(request.app.state, 'analysis_service'):
        request.app.state.analysis_service = AnalysisService(
            analysis_repo=repo_analysis,
            question_repo=repo_question,
            paper_repo=repo_paper,
        )
    return request.app.state.analysis_service


async def get_scrape_service(request: Request) -> ScrapeService:
    if not hasattr(request.app.state, 'scrape_service'):
        request.app.state.scrape_service = ScrapeService(
            paper_repo=repo_paper,
        )
    return request.app.state.scrape_service


async def get_filter_service(request: Request) -> FilterService:
    if not hasattr(request.app.state, 'filter_service'):
        request.app.state.filter_service = FilterService(
            paper_repo=repo_paper,
        )
    return request.app.state.filter_service


async def get_audit_service(request: Request) -> AuditService:
    if not hasattr(request.app.state, 'audit_service'):
        request.app.state.audit_service = AuditService(audit_repo=repo_audit)
    return request.app.state.audit_service


# ============ 原有引擎依赖注入（保持不变） ============

def get_scraper_manager(request: Request):
    return request.app.state.scraper_manager


def get_irt_model(request: Request):
    return request.app.state.irt_model


def get_kp_mapper(request: Request):
    return request.app.state.kp_mapper


def get_quality_analyzer(request: Request):
    return request.app.state.quality_analyzer


def get_simulator(request: Request):
    return request.app.state.simulator


def get_fitting_analyzer(request: Request):
    return request.app.state.fitting_analyzer


def get_paper_parser(request: Request):
    return request.app.state.paper_parser


def get_curriculum_analyzer(request: Request):
    return request.app.state.curriculum_analyzer


def get_quality_scorer(request: Request):
    return request.app.state.quality_scorer


def get_search_engine(request: Request):
    return request.app.state.search_engine


def get_dedup_engine(request: Request):
    return request.app.state.dedup_engine


def get_auto_scraper(request: Request):
    return request.app.state.auto_scraper


def get_paper_analyzer(request: Request):
    return request.app.state.paper_analyzer


def get_official_docs(request: Request):
    return request.app.state.official_docs


def get_app_context(request: Request) -> AppContext:
    """返回运行时集中化的应用上下文快照（app.state.ctx）。"""
    return request.app.state.ctx
