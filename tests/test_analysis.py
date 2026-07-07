"""阶段二（后端核心）：试卷分析 + 可插拔爬虫适配器 单元测试。

说明：本测试为纯 pytest 单测，无需 pytest-asyncio（异步函数用 asyncio.run 驱动）。
覆盖：
- analyze_paper 各维度分值在 0-100、综合分计算正确、报告可 JSON 序列化；
- analyze_papers_batch 并行返回数量与输入一致；
- LocalFixtureAdapter 解析 JSON / Markdown 样例；
- ScraperManager.collect_all 通过 local_fixture 数据源发现样例（不触网）。
"""
import asyncio
import json
import os
import sys

import pytest

# 将项目根目录加入 path，便于直接 python tests/test_analysis.py 运行
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from paper_analysis import PaperAnalyzer, analyze_paper, analyze_papers_batch  # noqa: E402
from scraper import (  # noqa: E402
    AdapterRegistry,
    ExtractedPaper,
    LocalFixtureAdapter,
    ScraperManager,
)
from config import DATA_SOURCES  # noqa: E402

FIXTURE_DIR = os.path.join("tests", "fixtures", "papers")


def _make_math_paper():
    """构造一份带 IRT 参数的小数学卷（dict 形式）。"""
    return {
        "title": "测试数学卷",
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


# ===================== 分析维度 =====================

def test_analyze_paper_dimensions_in_range():
    report = analyze_paper(_make_math_paper())
    dims = report["dimensions"]
    for name in ("difficulty", "knowledge_coverage", "type_distribution",
                 "discrimination", "reliability", "validity"):
        assert name in dims, f"缺少维度 {name}"
        assert 0 <= dims[name]["score"] <= 100, f"{name} 分值越界: {dims[name]['score']}"
    assert 0 <= report["composite"]["score"] <= 100
    assert report["composite"]["grade"] in ("优秀", "良好", "合格", "待改进")
    # 可视化数组：雷达 6 维、难度曲线与题数一致
    assert len(report["visualization"]["radar"]) == 6
    assert len(report["visualization"]["difficulty_curve"]) == report["question_count"]


def test_composite_weighted_sum():
    report = analyze_paper(_make_math_paper())
    dims = report["dimensions"]
    weights = report["composite"]["weights"]
    expected = round(sum(dims[k]["score"] * weights[k] for k in weights), 2)
    assert abs(expected - report["composite"]["score"]) < 0.01


def test_report_json_serializable():
    report = analyze_paper(_make_math_paper())
    # 必须可 JSON 序列化（结构化输出要求）
    blob = json.dumps(report, ensure_ascii=False, default=str)
    assert isinstance(blob, str) and len(blob) > 0


def test_analyze_empty_paper():
    report = analyze_paper({"title": "空卷", "subject": "math", "questions": []})
    assert report["question_count"] == 0
    assert report["composite"]["score"] == 0
    assert report["composite"]["grade"] == "待改进"


# ===================== 批量并行 =====================

def test_analyze_papers_batch_count_and_consistency():
    papers = [_make_math_paper(), _make_math_paper()]
    reports = asyncio.run(analyze_papers_batch(papers, max_workers=2))
    assert len(reports) == 2
    for r in reports:
        assert "error" not in r, f"批量分析异常: {r.get('error')}"
        assert r["question_count"] == 3
        assert 0 <= r["composite"]["score"] <= 100


# ===================== 爬虫适配器 =====================

def test_local_fixture_adapter_json():
    src_cfg = {
        "id": "fx", "name": "fixture", "adapter_type": "local_fixture",
        "enabled": True, "base_dir": FIXTURE_DIR, "format": "json",
    }
    adapter = LocalFixtureAdapter(src_cfg)
    items = adapter.discover("math", 2026)
    assert any(it["title"].startswith("sample_math") for it in items)
    target = next(it for it in items if it["title"].startswith("sample_math"))
    paper = adapter.fetch_and_parse(target)
    assert isinstance(paper, ExtractedPaper)
    assert len(paper.questions) == 3
    assert paper.questions[0].q_type == "choice"
    assert paper.questions[0].knowledge_points == ["2.2.1"]  # 显式知识点保留


def test_local_fixture_adapter_auto_markdown():
    src_cfg = {
        "id": "fx2", "name": "fixture", "adapter_type": "local_fixture",
        "enabled": True, "base_dir": FIXTURE_DIR, "format": "auto",
    }
    adapter = LocalFixtureAdapter(src_cfg)
    items = adapter.discover("chinese", 2026)
    md_item = next((it for it in items if it["title"].startswith("sample_chinese")), None)
    assert md_item is not None, "未发现 markdown 样例"
    paper = adapter.fetch_and_parse(md_item)
    assert paper is not None
    assert len(paper.questions) >= 1
    # 题型推断正确（含选择题）
    assert any(q.q_type == "choice" for q in paper.questions)


def test_scraper_manager_collect_all_fixtures():
    # 仅启用 local_fixture，避免任何网络请求
    sources = [s for s in DATA_SOURCES if s["id"] == "local_fixture"]
    assert sources, "配置缺少 local_fixture 数据源"
    mgr = ScraperManager(data_sources=sources)
    try:
        items = asyncio.run(mgr.collect_all(2026, ["math"]))
        assert any(it.get("type") == "fixture" for it in items), "未发现 fixture 候选"
    finally:
        asyncio.run(mgr.close())


def test_adapter_registry_has_defaults():
    available = AdapterRegistry.available()
    assert "local_fixture" in available
    assert "generic_web" in available


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
