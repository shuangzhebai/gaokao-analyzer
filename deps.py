"""
依赖注入（T03/T04）
从 app.state 获取在 lifespan 中初始化的引擎单例，以及数据库连接。
避免全局可变单例直接引用，提升可测试性与可维护性（Q-2）。
"""
from fastapi import Request

from models import get_db


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


def get_official_docs(request: Request):
    return request.app.state.official_docs
