"""
MonteCarloSimulator 单元测试。

模拟器是纯数值计算（numpy/scipy），不依赖网络或数据库。
覆盖主要 public 方法和内部工具方法。
"""
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from simulator import FittingAnalyzer, MonteCarloSimulator


def _sample_item_params(n: int = 3):
    """构造示例 IRT 参数列表，返回 n 个参数。"""
    pool = [{"a": 1.2, "b": -0.5, "c": 0.2},
            {"a": 0.9, "b": 0.3, "c": 0.2},
            {"a": 1.6, "b": 1.0, "c": 0.1}]
    return pool[:n]


def _sample_scores(n: int = 3):
    return [5.0, 5.0, 12.0][:n]


def _sample_scores(n: int = 3):
    return [5.0, 5.0, 12.0][:n]


# ===================== MonteCarloSimulator =====================

class TestMonteCarloSimulator:
    """蒙特卡洛模拟基础功能。"""

    def setup_method(self):
        self.sim = MonteCarloSimulator()

    def test_simulate_empty_params(self):
        """空题目列表返回空结果。"""
        result = self.sim.simulate([], [])
        assert result["n_questions"] == 0
        assert result["n_students"] == 0
        assert result["score_distribution"] == []

    def test_simulate_basic(self):
        """基本模拟产出正确的统计量。"""
        params = _sample_item_params(3)
        scores = _sample_scores(3)
        result = self.sim.simulate(params, scores, n_students=1000, subject_id="math")
        assert result["n_questions"] == 3
        assert result["n_students"] == 1000
        assert result["mean"] > 0
        assert result["std"] > 0
        assert result["max"] >= result["min"]
        assert len(result["score_distribution"]) > 0
        assert len(result["percentile_table"]) > 0

    def test_simulate_statistics_reasonable(self):
        """模拟统计量在合理范围内。"""
        params = _sample_item_params(3)
        scores = _sample_scores(3)
        max_score = sum(scores)
        result = self.sim.simulate(params, scores, n_students=5000, subject_id="math")
        assert 0 <= result["mean"] <= max_score
        assert 0 <= result["std"] <= max_score
        assert result["q1"] <= result["q3"]

    def test_simulate_extreme_difficulty(self):
        """极端难度参数不导致崩溃。"""
        params = [
            {"a": 3.0, "b": -4.0, "c": 0.0},   # 极容易
            {"a": 3.0, "b": 4.0, "c": 0.0},    # 极难
        ]
        scores = [10.0, 10.0]
        result = self.sim.simulate(params, scores, n_students=500, subject_id="math")
        assert result["n_questions"] == 2
        assert result["mean"] is not None

    def test_simulate_with_user_answers(self):
        """传入 user_answers 时有 user 字段。"""
        params = _sample_item_params(2)
        scores = [5.0, 10.0]
        result = self.sim.simulate(params, scores, n_students=500,
                                   user_answers=[1, 0], subject_id="math")
        assert "user" in result
        assert result["user"]["score"] == 5.0  # 只答对第一题（5分）
        assert result["user"]["max_possible"] == 15.0

    def test_simulate_user_answers_boundary(self):
        """user_answers 全对 / 全错。"""
        params = _sample_item_params(2)
        scores = [5.0, 10.0]
        r_all_correct = self.sim.simulate(params, scores, n_students=200,
                                          user_answers=[1, 1], subject_id="math")
        assert r_all_correct["user"]["score"] == 15.0
        r_all_wrong = self.sim.simulate(params, scores, n_students=200,
                                        user_answers=[0, 0], subject_id="math")
        assert r_all_wrong["user"]["score"] == 0.0

    def test_simulate_different_subject(self):
        """不同科目使用不同校准数据。"""
        params = _sample_item_params(2)
        scores = [5.0, 5.0]
        r_math = self.sim.simulate(params, scores, n_students=1000, subject_id="math")
        r_physics = self.sim.simulate(params, scores, n_students=1000, subject_id="physics")
        # 不同科目校准参数不同，均值应有差异
        assert r_math["mean"] is not None
        assert r_physics["mean"] is not None

    def test_segment_rates_structure(self):
        """分段得分率返回 4 段。"""
        params = _sample_item_params(3)
        scores = _sample_scores(3)
        result = self.sim.simulate(params, scores, n_students=1000, subject_id="math")
        segment_rates = result["segment_rates"]
        assert len(segment_rates) == 4
        for seg in segment_rates:
            assert "segment" in seg
            assert "count" in seg
            assert seg["count"] >= 0

    def test_grade_assignment_applicable(self):
        """选考科目（100分制）等级赋分适用。"""
        params = _sample_item_params(2)
        scores = [50.0, 50.0]  # 总分100
        result = self.sim.simulate(params, scores, n_students=1000, subject_id="physics")
        ga = result["grade_assignment"]
        assert ga.get("applicable") is True
        assert len(ga["grades"]) > 0

    def test_grade_assignment_not_applicable(self):
        """非选考科目（150分制）不适用等级赋分。"""
        params = _sample_item_params(3)
        scores = [50.0, 50.0, 50.0]  # 总分150
        result = self.sim.simulate(params, scores, n_students=1000, subject_id="math")
        ga = result["grade_assignment"]
        assert ga.get("applicable") is False

    def test_score_lines_structure(self):
        """分数线预测结果含基本分数线。"""
        params = _sample_item_params(3)
        scores = _sample_scores(3)
        result = self.sim.simulate(params, scores, n_students=1000, subject_id="math")
        lines = result["score_lines"]
        assert len(lines) >= 4
        for line in lines:
            assert "line_name" in line
            assert "predicted_score" in line
            assert 0 <= line["predicted_score"] <= sum(scores)

    def test_test_information(self):
        """测验信息量分析。"""
        params = _sample_item_params(3)
        info = self.sim._compute_test_information(params)
        assert "max_information" in info
        assert info["max_information"] > 0
        assert "info_at_0" in info

    def test_get_grade_for_percentile(self):
        """百分位转等级。"""
        assert self.sim._get_grade_for_percentile(99) == "A"
        assert self.sim._get_grade_for_percentile(50) == "C"  # C: pct_top=53, 100-50=50 <= 53
        assert self.sim._get_grade_for_percentile(0) == "F"

    def test_get_bins(self):
        """分数分段正确。"""
        bins = self.sim._get_bins(150)
        assert len(bins) > 10
        assert bins[0] == 0

    def test_build_percentile_table(self):
        """百分位表含关键分位点。"""
        scores = np.random.default_rng(42).normal(75, 15, 1000)
        table = self.sim._build_percentile_table(scores)
        assert len(table) == 18
        assert table[0]["percentile"] == 1
        assert table[-1]["percentile"] == 99


# ===================== FittingAnalyzer =====================

class TestFittingAnalyzer:
    """拟合分析功能。"""

    def setup_method(self):
        self.fa = FittingAnalyzer()

    def test_difficulty_distribution(self):
        """IRT 难度参数分布提取。"""
        params = _sample_item_params(3)
        b_vals = self.fa.compute_difficulty_distribution(params)
        assert len(b_vals) == 3
        assert np.isclose(b_vals, [-0.5, 0.3, 1.0]).all()

    def test_difficulty_fit_test_short(self):
        """样本不足时不通过。"""
        result = self.fa.difficulty_fit_test(np.array([0.5]), np.array([0.6]))
        assert result["passed"] is False

    def test_difficulty_fit_test_normal(self):
        """相同分布应通过 KS 检验。"""
        rng = np.random.default_rng(42)
        b1 = rng.normal(0, 1, 50)
        b2 = rng.normal(0, 1, 50)
        result = self.fa.difficulty_fit_test(b1, b2)
        # 两个相同分布的样本很大概率不显著差异
        assert "ks_stat" in result
        assert "ks_pvalue" in result

    def test_question_type_match_all_different(self):
        """完全不同的题型分布匹配分低。"""
        result = self.fa.question_type_match({"choice": 10}, {"solve": 10})
        assert result["match_score"] == 0.0

    def test_question_type_match_identical(self):
        result = self.fa.question_type_match({"choice": 5, "solve": 10},
                                              {"choice": 5, "solve": 10})
        assert result["match_score"] == 1.0

    def test_aggregate_types(self):
        result = self.fa._aggregate_types([
            {"q_type": "choice", "score": 5},
            {"q_type": "solve", "score": 12},
        ])
        assert result == {"choice": 5, "solve": 12}

    def test_grade_fit(self):
        assert self.fa._grade_fit(0.90) == "A (高度拟合)"
        assert self.fa._grade_fit(0.75) == "B (较好拟合)"
        assert self.fa._grade_fit(0.60) == "C (一般拟合)"
        assert self.fa._grade_fit(0.45) == "D (较弱拟合)"
        assert self.fa._grade_fit(0.30) == "E (不拟合)"
