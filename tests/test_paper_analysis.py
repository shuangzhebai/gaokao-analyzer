"""
PaperAnalyzer 各内部方法独立单元测试。

覆盖 LRUCache、难度评估、知识点覆盖、信度、效度、综合评分等内部逻辑。
不重复 test_analysis.py 已覆盖的 analyze_paper / analyze_papers_batch 集成测试。
"""
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from paper_analysis import LRUCache, PaperAnalyzer, analyze_paper
from simulator import MonteCarloSimulator


# ===================== LRUCache =====================

class TestLRUCache:
    """LRU 缓存线程安全基础功能。"""

    def test_put_and_get(self):
        cache = LRUCache(maxsize=5)
        cache.put("k1", 100)
        assert cache.get("k1") == 100

    def test_get_missing(self):
        cache = LRUCache(maxsize=5)
        assert cache.get("nonexistent") is None

    def test_maxsize_eviction(self):
        cache = LRUCache(maxsize=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # 应移除最早写入的 "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_contains(self):
        cache = LRUCache(maxsize=5)
        cache.put("x", 42)
        assert "x" in cache
        assert "y" not in cache

    def test_len(self):
        cache = LRUCache(maxsize=5)
        cache.put("a", 1)
        cache.put("b", 2)
        assert len(cache) == 2

    def test_move_to_end_on_get(self):
        """get 应将被访问项移到尾部，使较老项先被淘汰。"""
        cache = LRUCache(maxsize=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # 访问 "a" 使其变成最近使用
        cache.get("a")
        cache.put("d", 4)  # 应淘汰最久未用的 "b"
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("d") == 4


# ===================== PaperAnalyzer =====================

def _make_small_paper():
    """构造一份带 IRT 参数的小数学卷（dict 形式）。"""
    return {
        "title": "单元测试卷",
        "subject": "math",
        "year": 2026,
        "questions": [
            {"q_type": "choice", "content": "函数相关题", "score": 5,
             "knowledge_points": ["2.2.1"], "irt_a": 1.2, "irt_b": -0.5, "irt_c": 0.2},
            {"q_type": "fill", "content": "数列相关题", "score": 5,
             "knowledge_points": ["2.5.1"], "irt_a": 0.9, "irt_b": 0.3, "irt_c": 0.2},
            {"q_type": "solve", "content": "立体几何相关题", "score": 12,
             "knowledge_points": ["2.7.1"], "irt_a": 1.6, "irt_b": 1.0, "irt_c": 0.1},
        ],
    }


class TestPaperAnalyzerInternals:
    """PaperAnalyzer 内部方法独立测试（不依赖 analyze 主入口）。"""

    def test_analyze_with_direct_irt(self):
        """试题自带 IRT 参数时应走快路径，产出正确维度。"""
        analyzer = PaperAnalyzer(subject_id="math", n_students=2000, use_cache=False)
        report = analyzer.analyze(_make_small_paper())
        assert report["question_count"] == 3
        assert report["subject"] == "math"
        dims = report["dimensions"]
        for key in ("difficulty", "knowledge_coverage", "type_distribution",
                     "discrimination", "reliability", "validity"):
            assert key in dims
            assert 0 <= dims[key]["score"] <= 100, f"{key} score={dims[key]['score']} out of range"
        assert report["composite"]["grade"] in ("优秀", "良好", "合格", "待改进")

    def test_analyze_no_irt_params_falls_back_to_estimation(self):
        """题目无 IRT 参数时触发估计，结果仍有效。"""
        paper = {
            "title": "带估计的卷",
            "subject": "math",
            "year": 2026,
            "questions": [
                {"q_type": "choice", "content": "选择函数题", "score": 5},
                {"q_type": "solve", "content": "立体几何大题", "score": 12},
            ],
        }
        analyzer = PaperAnalyzer(subject_id="math", n_students=1000, use_cache=False)
        report = analyzer.analyze(paper)
        assert report["question_count"] == 2
        assert 0 <= report["composite"]["score"] <= 100

    def test_paper_title_subject_year(self):
        """_paper_title / _paper_subject / _paper_year 静态方法。"""
        paper = {"title": "T", "subject": "physics", "year": 2025}
        assert PaperAnalyzer._paper_title(paper) == "T"
        assert PaperAnalyzer._paper_subject(paper) == "physics"
        assert PaperAnalyzer._paper_year(paper) == 2025

    def test_paper_title_obj(self):
        """对象类型试卷的 title/subject/year 提取。"""
        class MockPaper:
            title = "Obj卷"
            subject = "chinese"
            year = 2024
        p = MockPaper()
        assert PaperAnalyzer._paper_title(p) == "Obj卷"
        assert PaperAnalyzer._paper_subject(p) == "chinese"
        assert PaperAnalyzer._paper_year(p) == 2024

    def test_empty_report(self):
        """空报告格式正确。"""
        analyzer = PaperAnalyzer(subject_id="math", use_cache=False)
        report = analyzer._empty_report({"title": "空卷", "subject": "math"})
        assert report["question_count"] == 0
        assert report["composite"]["score"] == 0
        assert report["composite"]["grade"] == "待改进"
        assert report["dimensions"]["difficulty"]["score"] == 0

    def test_normalize_questions_empty(self):
        """_normalize_questions 处理空卷。"""
        analyzer = PaperAnalyzer(subject_id="math", use_cache=False)
        assert analyzer._normalize_questions({}) == []
        assert analyzer._normalize_questions({"questions": []}) == []
        assert analyzer._normalize_questions("invalid_string") == []

    def test_normalize_questions_with_irt(self):
        """_normalize_questions 保留 IRT 参数。"""
        analyzer = PaperAnalyzer(subject_id="math", use_cache=False)
        paper = _make_small_paper()
        qs = analyzer._normalize_questions(paper)
        assert len(qs) == 3
        assert qs[0]["irt_a"] == 1.2
        assert qs[0]["irt_b"] == -0.5

    def test_suggest_returns_reasonable_advice(self):
        """_suggest 静态方法返回合理的改进建议。"""
        for dim in ("difficulty", "knowledge_coverage", "type_distribution",
                     "discrimination", "reliability", "validity"):
            tip = PaperAnalyzer._suggest(dim)
            assert isinstance(tip, str) and len(tip) > 5

    def test_cache_integration(self):
        """use_cache=True 时缓存生效，重复分析速度提升。"""
        analyzer = PaperAnalyzer(subject_id="math", n_students=1000, use_cache=True)
        paper = _make_small_paper()
        r1 = analyzer.analyze(paper)
        r2 = analyzer.analyze(paper)
        assert r1["question_count"] == r2["question_count"]
        assert r1["composite"]["score"] == r2["composite"]["score"]
