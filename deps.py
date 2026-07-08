"""
依赖注入（T03/T04/T05）
从 app.state 获取在 lifespan 中初始化的引擎单例，以及数据库连接。
避免全局可变单例直接引用，提升可测试性与可维护性（Q-2）。

T01 扩展：新增 service 依赖注入函数，注册 PaperService / AnalysisService /
ScrapeService / FilterService 到 app.state（惰性初始化）。

T05 扩展：新增 AuthService / UserRepository 及 JWT 认证相关依赖。
"""
from typing import Any

from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED

from models import get_db
from app_context import AppContext

from repositories.paper_repo import PaperRepository
from repositories.question_repo import QuestionRepository
from repositories.analysis_repo import AnalysisRepository
from repositories.audit_repo import AuditRepository
from repositories.user_repo import UserRepository

from services.paper_service import PaperService
from services.analysis_service import AnalysisService
from services.scrape_service import ScrapeService
from services.filter_service import FilterService
from services.audit_service import AuditService
from services.auth_service import AuthService

# ============ Repository 单例（无状态，可跨请求复用） ============
repo_paper = PaperRepository()
repo_question = QuestionRepository()
repo_analysis = AnalysisRepository()
repo_audit = AuditRepository()
repo_user = UserRepository()


# ============ Service 惰性初始化（防止 lifespan 之前被意外调用） ============

async def get_paper_service(request: Request) -> Any:
    if not hasattr(request.app.state, 'paper_service'):
        request.app.state.paper_service = PaperService(
            paper_repo=repo_paper,
            question_repo=repo_question,
            analysis_repo=repo_analysis,
        )
    return request.app.state.paper_service


async def get_analysis_service(request: Request) -> Any:
    if not hasattr(request.app.state, 'analysis_service'):
        request.app.state.analysis_service = AnalysisService(
            analysis_repo=repo_analysis,
            question_repo=repo_question,
            paper_repo=repo_paper,
        )
    return request.app.state.analysis_service


async def get_scrape_service(request: Request) -> Any:
    if not hasattr(request.app.state, 'scrape_service'):
        request.app.state.scrape_service = ScrapeService(
            paper_repo=repo_paper,
        )
    return request.app.state.scrape_service


async def get_filter_service(request: Request) -> Any:
    if not hasattr(request.app.state, 'filter_service'):
        request.app.state.filter_service = FilterService(
            paper_repo=repo_paper,
        )
    return request.app.state.filter_service


async def get_audit_service(request: Request) -> Any:
    if not hasattr(request.app.state, 'audit_service'):
        request.app.state.audit_service = AuditService(audit_repo=repo_audit)
    return request.app.state.audit_service


# ============ 原有引擎依赖注入（保持不变） ============

def get_scraper_manager(request: Request) -> Any:
    return request.app.state.scraper_manager


def get_irt_model(request: Request) -> Any:
    return request.app.state.irt_model


def get_kp_mapper(request: Request) -> Any:
    return request.app.state.kp_mapper


def get_quality_analyzer(request: Request) -> Any:
    return request.app.state.quality_analyzer


def get_simulator(request: Request) -> Any:
    return request.app.state.simulator


def get_fitting_analyzer(request: Request) -> Any:
    return request.app.state.fitting_analyzer


def get_paper_parser(request: Request) -> Any:
    return request.app.state.paper_parser


def get_curriculum_analyzer(request: Request) -> Any:
    return request.app.state.curriculum_analyzer


def get_quality_scorer(request: Request) -> Any:
    return request.app.state.quality_scorer


def get_search_engine(request: Request) -> Any:
    return request.app.state.search_engine


def get_dedup_engine(request: Request) -> Any:
    return request.app.state.dedup_engine


def get_auto_scraper(request: Request) -> Any:
    return request.app.state.auto_scraper


def get_paper_analyzer(request: Request) -> Any:
    return request.app.state.paper_analyzer


def get_official_docs(request: Request) -> Any:
    return request.app.state.official_docs


def get_app_context(request: Request) -> Any:
    """返回运行时集中化的应用上下文快照（app.state.ctx）。"""
    return request.app.state.ctx


# ============ T05: Auth 依赖注入 ============


async def get_auth_service(request: Request) -> AuthService:
    """惰性初始化并返回 AuthService 单例。"""
    if not hasattr(request.app.state, 'auth_service'):
        request.app.state.auth_service = AuthService(user_repo=repo_user)
    result = request.app.state.auth_service
    return result  # type: ignore[no-any-return]


async def get_current_user(request: Request) -> dict[str, Any]:
    """从 JWT token 提取当前用户。若 token 无效，抛 401。"""
    user = getattr(request.state, 'user', None)
    if user is None or not isinstance(user, dict):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="未提供有效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(required_role: str) -> Any:
    """依赖注入工厂：验证用户角色是否满足要求。

    角色优先级: admin(0) > teacher(1) > viewer(2)。
    拥有 higher 或同优先级角色的用户可以访问。

    Args:
        required_role: 所需的最低角色 ('admin', 'teacher', 'viewer')

    Returns:
        依赖注入函数
    """
    async def _check_role(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        from services.auth_service import ROLE_PRIORITY
        user_role = current_user.get("role", "viewer")
        required_priority = ROLE_PRIORITY.get(required_role, 99)
        user_priority = ROLE_PRIORITY.get(user_role, 99)
        if user_priority > required_priority:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足。需要 '{required_role}' 角色，当前角色: '{user_role}'",
            )
        return current_user
    return _check_role
