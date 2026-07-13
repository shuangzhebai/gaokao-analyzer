"""
services 子包：业务层，编排逻辑 + 管理 commit()。
使用延迟导入避免干扰 standalone 测试。
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .paper_service import PaperService
    from .analysis_service import AnalysisService
    from .scrape_service import ScrapeService
    from .filter_service import FilterService

__all__ = ["PaperService", "AnalysisService", "ScrapeService", "FilterService"]


def _lazy_import(name: str):
    """延迟导入，避免 import chain 阻断独立测试。"""
    import importlib
    return importlib.import_module(f".{name}", __package__)
