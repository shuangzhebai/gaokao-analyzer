"""T04: 智能组卷引擎测试。"""

import pytest

from engines.composition_engine import CompositionEngine, CompositionResult


class TestGreedySolver:
    """贪心求解器测试（OR-Tools 不可用时的退路）。"""

    @pytest.fixture
    def engine(self):
        return CompositionEngine()

    @pytest.fixture
    def sample_questions(self):
        return [
            {"id": 1, "question_type_id": 1, "score": 5, "source": "real", "irt_b": -0.5, "irt_a": 1.2},
            {"id": 2, "question_type_id": 1, "score": 5, "source": "mock", "irt_b": 0.0, "irt_a": 0.8},
            {"id": 3, "question_type_id": 1, "score": 5, "source": "real", "irt_b": 0.3, "irt_a": 1.5},
            {"id": 4, "question_type_id": 2, "score": 5, "source": "mock", "irt_b": -0.2, "irt_a": 1.0},
            {"id": 5, "question_type_id": 2, "score": 10, "source": "real", "irt_b": 0.5, "irt_a": 1.8},
            {"id": 6, "question_type_id": 3, "score": 10, "source": "mock", "irt_b": 1.0, "irt_a": 0.5},
            {"id": 7, "question_type_id": 3, "score": 10, "source": "real", "irt_b": -1.0, "irt_a": 2.0},
            {"id": 8, "question_type_id": 3, "score": 10, "source": "mock", "irt_b": 0.2, "irt_a": 1.1},
        ]

    def test_basic_solve(self, engine, sample_questions):
        """基础求解：应返回正确数量的题目。"""
        constraints = {
            "total_count": 5,
            "types": [
                {"id": 1, "count": 2, "score": 5},
                {"id": 2, "count": 1, "score": 5},
                {"id": 3, "count": 2, "score": 10},
            ],
            "prefer_real_exam": True,
        }
        result = engine.solve(sample_questions, constraints)
        assert isinstance(result, CompositionResult)
        assert len(result.question_ids) == 5
        assert result.constraints_satisfied is True

    def test_real_exam_priority(self, engine, sample_questions):
        """真题优先：应优先选择 source='real' 的题目。"""
        constraints = {
            "total_count": 4,
            "types": [
                {"id": 1, "count": 2, "score": 5},
                {"id": 3, "count": 2, "score": 10},
            ],
            "prefer_real_exam": True,
        }
        result = engine.solve(sample_questions, constraints)
        # 至少有一道真题
        selected = [q for q in sample_questions if q["id"] in result.question_ids]
        real_count = sum(1 for s in selected if s["source"] == "real")
        assert real_count >= 1

    def test_no_real_exam(self, engine, sample_questions):
        """不要求真题优先时也应正常求解。"""
        constraints = {
            "total_count": 3,
            "types": [{"id": 1, "count": 2, "score": 5}],
            "prefer_real_exam": False,
        }
        result = engine.solve(sample_questions, constraints)
        assert len(result.question_ids) >= 1

    def test_empty_questions(self, engine):
        """空题目列表应返回空结果。"""
        constraints = {"total_count": 5, "types": [], "prefer_real_exam": True}
        result = engine.solve([], constraints)
        assert len(result.question_ids) == 0
        assert result.total_score == 0

    def test_insufficient_questions(self, engine, sample_questions):
        """题目不足时返回全部可用题目。"""
        constraints = {
            "total_count": 100,  # 远超可用题目数
            "types": [],
            "prefer_real_exam": True,
        }
        result = engine.solve(sample_questions, constraints)
        assert len(result.question_ids) <= len(sample_questions)


class TestPrecheckQuality:
    """质量预检测试。"""

    def test_precheck_returns_dict(self):
        """质量预检应返回字典格式的报告。"""
        engine = CompositionEngine()
        report = engine.precheck_quality([1, 2, 3])
        assert isinstance(report, dict)
        assert "difficulty_distribution" in report
        assert "knowledge_coverage" in report
        assert "reliability_estimate" in report
        assert "warnings" in report

    def test_precheck_empty(self):
        """空题目列表也应返回报告。"""
        engine = CompositionEngine()
        report = engine.precheck_quality([])
        assert isinstance(report, dict)
        assert "warnings" in report


class TestCompositionResult:
    """CompositionResult 测试。"""

    def test_to_dict(self):
        result = CompositionResult(
            question_ids=[1, 2, 3],
            total_score=30.0,
            constraints_satisfied=True,
            objective_score=10.0,
            quality_report={"test": "report"},
        )
        d = result.to_dict()
        assert d["question_ids"] == [1, 2, 3]
        assert d["total_score"] == 30.0
        assert d["constraints_satisfied"] is True
        assert d["objective_score"] == 10.0
        assert d["quality_report"]["test"] == "report"

    def test_default_quality_report(self):
        result = CompositionResult(
            question_ids=[], total_score=0,
            constraints_satisfied=False, objective_score=0,
        )
        assert result.quality_report == {}
