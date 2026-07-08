"""P1-03: 可插拔分析器体系 — BaseAnalyzer 抽象基类 + AnalyzerRegistry。"""

from abc import ABC, abstractmethod
from typing import Any


class BaseAnalyzer(ABC):
    """分析器插件基类。所有维度分析器继承此类并实现 analyze 方法。"""

    @abstractmethod
    async def analyze(
        self, db: Any, paper_id: int, **kwargs: Any
    ) -> dict[str, Any]:
        """对指定试卷执行本维度的分析。

        Args:
            db: 数据库连接
            paper_id: 试卷 ID
            **kwargs: 分析参数（如权重、配置等）

        Returns:
            包含分析结果的 dict，至少含 'dimension' 和 'score' 字段
        """
        ...

    @property
    @abstractmethod
    def dimension_name(self) -> str:
        """维度名称（英文标识），如 'difficulty', 'knowledge_coverage'"""
        ...


class AnalyzerRegistry:
    """分析器注册表。支持运行时注册/获取/查询。"""

    _analyzers: dict[str, type[BaseAnalyzer]] = {}

    @classmethod
    def register(cls, analyzer_cls: type[BaseAnalyzer]) -> type[BaseAnalyzer]:
        """注册一个分析器类。"""
        name = analyzer_cls.dimension_name
        # 支持类方法或实例属性
        if not isinstance(name, str):
            name = analyzer_cls().dimension_name
        cls._analyzers[name] = analyzer_cls
        return analyzer_cls

    @classmethod
    def get(cls, name: str) -> type[BaseAnalyzer] | None:
        """获取指定名称的分析器类。"""
        return cls._analyzers.get(name.lower())

    @classmethod
    def list_analyzers(cls) -> list[str]:
        """列出所有已注册的分析器名称。"""
        return list(cls._analyzers.keys())

    @classmethod
    def create_all(cls) -> dict[str, BaseAnalyzer]:
        """创建所有已注册分析器的实例。"""
        return {
            name: cls_def()
            for name, cls_def in cls._analyzers.items()
        }
