"""P1-03: 分析器插件化测试。"""

import pytest

from analyzers import BaseAnalyzer, AnalyzerRegistry
from analyzers.impl import (
    DifficultyAnalyzer, KnowledgeCoverageAnalyzer, TypeDistributionAnalyzer,
    DiscriminationAnalyzer, ReliabilityAnalyzer, ValidityAnalyzer,
)


class TestAnalyzerRegistry:
    """AnalyzerRegistry 基础功能测试。"""

    def test_all_six_analyzers_registered(self) -> None:
        names = AnalyzerRegistry.list_analyzers()
        assert len(names) == 6
        assert "difficulty" in names
        assert "knowledge_coverage" in names
        assert "type_distribution" in names
        assert "discrimination" in names
        assert "reliability" in names
        assert "validity" in names

    def test_get_analyzer_returns_class(self) -> None:
        cls = AnalyzerRegistry.get("difficulty")
        assert cls is not None
        assert cls == DifficultyAnalyzer

    def test_get_unknown_analyzer_returns_none(self) -> None:
        cls = AnalyzerRegistry.get("non_existent")
        assert cls is None

    def test_create_all_returns_instances(self) -> None:
        instances = AnalyzerRegistry.create_all()
        assert len(instances) == 6
        for name, inst in instances.items():
            assert isinstance(inst, BaseAnalyzer)
            assert inst.dimension_name == name

    def test_dimension_names_correct(self) -> None:
        assert DifficultyAnalyzer().dimension_name == "difficulty"
        assert KnowledgeCoverageAnalyzer().dimension_name == "knowledge_coverage"
        assert DiscriminationAnalyzer().dimension_name == "discrimination"
