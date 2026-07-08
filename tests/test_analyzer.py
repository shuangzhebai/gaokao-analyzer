"""
IRTModel / KnowledgeMapper / QualityAnalyzer 纯函数单元测试。

这些类位于 analyzer.py 中，不依赖网络或数据库，属于纯计算逻辑，
适合直接构造输入验证输出。
"""
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analyzer import IRTModel, KnowledgeMapper, QualityAnalyzer


# ===================== IRTModel =====================

class TestIRTModel:
    """IRT 三参数模型基础功能。"""

    def setup_method(self):
        self.irt = IRTModel()

    def test_icc_single_value(self):
        """单点 ICC 计算：给定 theta/a/b/c 返回概率在 (0,1)。"""
        p = self.irt.icc(0.0, a=1.0, b=0.0, c=0.0)
        assert 0 < p < 1
        assert p == pytest.approx(0.5, abs=0.01)  # theta=b=0 时 P=0.5

    def test_icc_with_guessing(self):
        """猜测系数 c>0 使概率下界为 c 而非 0。"""
        p = self.irt.icc(-4.0, a=1.0, b=0.0, c=0.25)
        assert p >= 0.25

    def test_icc_vectorized(self):
        """向量化 ICC 返回与标量一致的结果。"""
        thetas = np.array([-2.0, 0.0, 2.0])
        vec = self.irt.icc_vectorized(thetas, a=1.0, b=0.0, c=0.0)
        assert vec.shape == (3,)
        for t, v in zip(thetas, vec):
            assert v == pytest.approx(self.irt.icc(t, 1.0, 0.0, 0.0), abs=1e-6)

    def test_log_likelihood_returns_positive(self):
        """负对数似然应为正值（prob<1 时）。"""
        thetas = np.array([-1.0, 0.0, 1.0])
        responses = np.array([0, 1, 1])
        ll = self.irt.log_likelihood([1.0, 0.0, 0.0], thetas, responses)
        assert ll > 0

    def test_estimate_parameters_basic(self):
        """已知生成参数能正确估计。"""
        rng = np.random.default_rng(42)
        thetas = rng.normal(0, 1, 200)
        # 用已知参数生成作答
        known_a, known_b, known_c = 1.5, 0.0, 0.1
        prob = known_c + (1 - known_c) / (1 + np.exp(-known_a * (thetas - known_b)))
        responses = (rng.random(200) < prob).astype(int)
        params = self.irt.estimate_parameters(thetas, responses)
        assert "a" in params and "b" in params and "c" in params
        # 参数应在合理范围内（估计值未必精确但应正数）
        assert 0.3 <= params["a"] <= 3.0
        assert -4.0 <= params["b"] <= 4.0

    def test_estimate_parameters_all_same(self):
        """所有考生答同一结果时仍返回默认参数。"""
        rng = np.random.default_rng(42)
        thetas = rng.normal(0, 1, 100)
        responses = np.ones(100, dtype=int)  # 全对
        params = self.irt.estimate_parameters(thetas, responses)
        assert "a" in params

    def test_estimate_all_questions(self):
        """批量估计。"""
        rng = np.random.default_rng(42)
        thetas = rng.normal(0, 1, 200)
        matrix = rng.binomial(1, 0.6, (200, 3))
        params_list = self.irt.estimate_all_questions(thetas, matrix)
        assert len(params_list) == 3
        for p in params_list:
            assert p["question_index"] in (0, 1, 2)

    def test_estimate_ability_eap(self):
        """EAP 能力值估计返回合理结果。"""
        rng = np.random.default_rng(42)
        thetas = rng.normal(0, 1, 200)
        resp = rng.binomial(1, 0.6, 200)
        matrix = resp.reshape(-1, 1)
        params_list = [{"a": 1.0, "b": 0.0, "c": 0.1, "question_index": 0}]
        # 用估计的参数来测试 estimate_ability
        params = self.irt.estimate_parameters(thetas, resp)
        params["question_index"] = 0
        ability = self.irt.estimate_ability(np.array([1]), [params])
        assert isinstance(ability, float)

    def test_information_function(self):
        """信息函数在 theta=b 附近最大。"""
        info_at_b = self.irt.information_function(0.0, a=1.5, b=0.0, c=0.0)
        info_far = self.irt.information_function(-4.0, a=1.5, b=0.0, c=0.0)
        assert info_at_b >= info_far

    def test_information_function_zero(self):
        """极端参数下信息函数返回 0 不抛异常。"""
        info = self.irt.information_function(0.0, a=0.3, b=0.0, c=0.99)
        assert info >= 0

    def test_test_information(self):
        """测验信息函数为各题之和。"""
        items = [{"a": 1.0, "b": 0.0, "c": 0.0}, {"a": 1.5, "b": 0.5, "c": 0.1}]
        total = self.irt.test_information(0.0, items)
        assert total > 0

    def test_standard_error(self):
        """测量标准误为正数或 inf。"""
        items = [{"a": 1.0, "b": 0.0, "c": 0.0}]
        se = self.irt.standard_error(0.0, items)
        assert se > 0 or se == float("inf")


# ===================== KnowledgeMapper =====================

class TestKnowledgeMapper:
    """知识点映射引擎。"""

    def setup_method(self):
        self.mapper = KnowledgeMapper()

    def test_map_math_keywords(self):
        """包含关键词的题目应映射到对应知识点。"""
        kps = self.mapper.map_question("函数与导数综合题", "math")
        assert "2.2.1" in kps or "2.3.1" in kps

    def test_map_unknown_subject(self):
        """未知科目返回空列表。"""
        kps = self.mapper.map_question("任何内容", "unknown_subject")
        assert kps == []

    def test_map_no_match(self):
        """无关键词匹配时返回空列表。"""
        kps = self.mapper.map_question("这是一道普通题", "math")
        assert kps == []

    def test_map_physics(self):
        """物理关键词映射。"""
        kps = self.mapper.map_question("牛顿第二定律的应用", "physics")
        assert "4.1.2" in kps

    def test_compute_coverage_all_match(self):
        """完全匹配时覆盖率指标为 1。"""
        result = self.mapper.compute_coverage(["2.2.1", "2.5.1"], ["2.2.1", "2.5.1"])
        assert result["jaccard"] == 1.0
        assert result["f1"] == 1.0

    def test_compute_coverage_no_match(self):
        """完全不匹配时指标为 0。"""
        result = self.mapper.compute_coverage(["2.2.1"], ["2.5.1"])
        assert result["jaccard"] == 0.0
        assert result["recall"] == 0.0

    def test_compute_coverage_empty_ref(self):
        """参考集为空时全部返回 0。"""
        result = self.mapper.compute_coverage(["2.2.1"], [])
        assert result["jaccard"] == 0.0
        assert result["precision"] == 0.0

    def test_compute_coverage_empty_both(self):
        """双方都为空。"""
        result = self.mapper.compute_coverage([], [])
        assert result["jaccard"] == 0.0

    def test_compute_coverage_partial(self):
        """部分匹配时输出正确交集/差集。"""
        result = self.mapper.compute_coverage(["2.2.1", "2.5.1", "2.9.1"], ["2.2.1", "2.7.1"])
        assert result["jaccard"] == 0.25  # 1 intersected / 4 union
        assert sorted(result["intersection"]) == ["2.2.1"]
        assert "2.7.1" in result["missing"]
        assert "2.9.1" in result["extra"]


# ===================== QualityAnalyzer =====================

class TestQualityAnalyzer:
    """试题质量分析器静态方法。"""

    def test_discrimination(self):
        assert QualityAnalyzer.discrimination({"a": 1.5}) == 1.5
        assert QualityAnalyzer.discrimination({"a": 0}) == 0.0
        assert QualityAnalyzer.discrimination({}) == 0.0

    def test_difficulty_index(self):
        assert QualityAnalyzer.difficulty_index(0.75) == 0.75
        assert QualityAnalyzer.difficulty_index(0.0) == 0.0

    def test_point_biserial_mismatch_length(self):
        result = QualityAnalyzer.point_biserial(np.array([1, 2]), np.array([0]))
        assert result == 0.0

    def test_point_biserial_single_value(self):
        result = QualityAnalyzer.point_biserial(np.array([1, 2, 3]), np.array([1, 1, 1]))
        assert result == 0.0

    def test_point_biserial_normal(self):
        scores = np.array([10, 20, 30, 40, 50])
        items = np.array([0, 0, 1, 1, 1])
        result = QualityAnalyzer.point_biserial(scores, items)
        assert isinstance(result, float)

    def test_cronbach_alpha_single_item(self):
        matrix = np.array([[1], [0], [1]])
        assert QualityAnalyzer.cronbach_alpha(matrix) == 0.0

    def test_cronbach_alpha_no_variance(self):
        matrix = np.array([[1, 1], [1, 1], [1, 1]])
        assert QualityAnalyzer.cronbach_alpha(matrix) == 0.0

    def test_cronbach_alpha_normal(self):
        matrix = np.array([[1, 0, 1], [0, 1, 0], [1, 1, 0], [0, 0, 1]], dtype=float)
        alpha = QualityAnalyzer.cronbach_alpha(matrix)
        # 小矩阵可能产生负 alpha，但应当是可计算的 float
        assert isinstance(alpha, (float, np.floating))

    def test_quality_score_best(self):
        """最优参数应得接近满分。"""
        score = QualityAnalyzer.quality_score(1.3, 0.9, 0.5)
        assert score >= 70

    def test_quality_score_floor(self):
        """最差参数应得低分。"""
        score = QualityAnalyzer.quality_score(0.0, 0.0, 0.0)
        assert score <= 10

    def test_quality_score_boundary_difficulty(self):
        """难度边界值评分。"""
        s1 = QualityAnalyzer.quality_score(0.5, 0.5, 0.3)  # 边界最优
        s2 = QualityAnalyzer.quality_score(0.5, 0.5, 0.25)  # 第二档
        s3 = QualityAnalyzer.quality_score(0.5, 0.5, 0.15)  # 第三档
        s4 = QualityAnalyzer.quality_score(0.5, 0.5, 0.05)  # 最差档
        assert s1 >= s2 >= s3 >= s4
