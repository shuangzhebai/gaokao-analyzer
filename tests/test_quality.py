"""T03: IRT+CTT 混合质量诊断引擎测试。"""

import math

import numpy as np
import pytest

from engines.hybrid_quality import HybridQualityEngine


class TestCTTIndicators:
    """CTT 经典指标计算测试。"""

    def test_empty_responses(self):
        engine = HybridQualityEngine()
        result = engine.compute_ctt_indicators([])
        assert result["p_value"] == 0
        assert result["discrimination"] == 0
        assert result["point_biserial"] == 0

    def test_all_correct(self):
        engine = HybridQualityEngine()
        responses = [
            {"user_id": 1, "score": 1, "max_score": 1, "is_correct": 1},
            {"user_id": 2, "score": 1, "max_score": 1, "is_correct": 1},
            {"user_id": 3, "score": 1, "max_score": 1, "is_correct": 1},
        ]
        result = engine.compute_ctt_indicators(responses)
        assert result["p_value"] == 1.0
        assert result["discrimination"] == 0.0  # 全对，区分度为 0
        assert result["variance"] == 0.0

    def test_half_correct(self):
        engine = HybridQualityEngine()
        responses = [
            {"user_id": 1, "score": 1, "max_score": 1, "is_correct": 1},
            {"user_id": 2, "score": 1, "max_score": 1, "is_correct": 1},
            {"user_id": 3, "score": 0, "max_score": 1, "is_correct": 0},
            {"user_id": 4, "score": 0, "max_score": 1, "is_correct": 0},
        ]
        result = engine.compute_ctt_indicators(responses)
        assert result["p_value"] == 0.5
        assert 0 <= result["discrimination"] <= 1.0

    def test_discrimination_high_low_groups(self):
        """验证高分组-低分组区分度计算。"""
        engine = HybridQualityEngine()
        # 前 5 人高分全对，后 5 人低分全错
        responses = [
            {"user_id": i, "score": 1, "max_score": 1, "is_correct": 1}
            for i in range(5)
        ] + [
            {"user_id": i, "score": 0, "max_score": 1, "is_correct": 0}
            for i in range(5, 10)
        ]
        result = engine.compute_ctt_indicators(responses)
        assert result["p_value"] == 0.5
        # 高分组全对(1.0) - 低分组全错(0.0) = 1.0
        # 但由于 27% 分位取整，10*0.27≈2.7→2人，所以高分组前2人全对=1.0，低分组后2人全错=0.0
        assert result["discrimination"] == 1.0


class TestReliability:
    """Cronbach α 信度系数测试。"""

    def test_single_item_returns_zero(self):
        engine = HybridQualityEngine()
        scores = np.array([[1], [0], [1]])
        alpha = engine.compute_reliability(scores)
        assert alpha == 0.0

    def test_perfect_reliability(self):
        """所有题目的作答完全一致 → α = 1.0。"""
        engine = HybridQualityEngine()
        # 2 道题，3 名学生，每人两题得分相同
        scores = np.array([
            [1, 1],
            [1, 1],
            [0, 0],
        ])
        alpha = engine.compute_reliability(scores)
        assert alpha == 1.0

    def test_zero_variance_returns_zero(self):
        engine = HybridQualityEngine()
        scores = np.array([
            [1, 1],
            [1, 1],
            [1, 1],
        ])
        alpha = engine.compute_reliability(scores)
        assert alpha == 0.0


class Test6DReport:
    """6 维质量报告生成测试。"""

    def test_basic_report(self):
        engine = HybridQualityEngine()
        report = engine.generate_6d_report(
            question_id=1,
            ctt_stats={"p_value": 0.75, "discrimination": 0.6, "point_biserial": 0.5, "variance": 0.2},
            irt_params={"a": 1.5, "b": -0.5, "c": 0.2, "cfi": 0.95, "tli": 0.93, "rmsea": 0.05},
        )
        assert report["question_id"] == 1
        assert len(report["dimensions"]) == 6
        assert "difficulty" in report["dimensions"]
        assert "discrimination" in report["dimensions"]
        assert "reliability" in report["dimensions"]
        assert "validity" in report["dimensions"]
        assert "knowledge_coverage" in report["dimensions"]
        assert "type_match" in report["dimensions"]
        assert report["overall_score"] > 0

    def test_report_without_irt(self):
        """仅 CTT 数据应能生成报告。"""
        engine = HybridQualityEngine()
        report = engine.generate_6d_report(
            question_id=2,
            ctt_stats={"p_value": 0.5, "discrimination": 0.3, "point_biserial": 0.2, "variance": 0.25},
        )
        assert report["question_id"] == 2
        assert report["irt_parameters"] == {}
        assert "p_value" in report["ctt_indicators"]
        assert report["dimensions"]["difficulty"] == 0.5  # 1 - 0.5 = 0.5

    def test_report_without_data(self):
        """无任何数据时应使用默认值。"""
        engine = HybridQualityEngine()
        report = engine.generate_6d_report(question_id=3)
        assert report["question_id"] == 3
        for dim, val in report["dimensions"].items():
            assert 0 <= val <= 1.0

    def test_irt_b_to_score(self):
        """IRT b 参数映射到 [0,1] 区间。"""
        # b=0 → 0.5
        score_zero = HybridQualityEngine._irt_b_to_score(0)
        assert abs(score_zero - 0.5) < 0.01
        # b=-3 → 接近 0.05（极简单）
        score_easy = HybridQualityEngine._irt_b_to_score(-3)
        assert score_easy < 0.1
        # b=3 → 接近 0.95（极难）
        score_hard = HybridQualityEngine._irt_b_to_score(3)
        assert score_hard > 0.9


class TestIntegration:
    """混合诊断集成测试。"""

    def test_analyze_workflow(self):
        """验证 analyze → generate_6d_report 完整流程。"""
        engine = HybridQualityEngine()
        # 模拟 20 名学生的作答
        np.random.seed(42)
        responses = [
            {"user_id": i, "score": 1 if np.random.random() > 0.4 else 0,
             "max_score": 1, "is_correct": 1 if np.random.random() > 0.4 else 0}
            for i in range(20)
        ]
        ctt = engine.compute_ctt_indicators(responses)
        assert "p_value" in ctt
        assert 0 <= ctt["p_value"] <= 1

        # 模拟 IRT 参数
        irt_params = {"a": 1.2, "b": 0.3, "c": 0.15}
        report = engine.generate_6d_report(1, ctt_stats=ctt, irt_params=irt_params)
        assert report["question_id"] == 1
        assert report["overall_score"] > 0
        assert report["irt_parameters"]["a"] == 1.2
        assert report["irt_parameters"]["b"] == 0.3
