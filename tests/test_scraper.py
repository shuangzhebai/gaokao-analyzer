"""
ScraperManager / AdapterRegistry / Fetcher 单元测试。

覆盖：
- AdapterRegistry 注册、获取、可用列表
- Fetcher 初始化与 User-Agent 轮换
- BaseSourceAdapter 工具方法（_classify_q_type / _guess_score / _map_knowledge / _difficulty_tag）
- LocalFixtureAdapter 发现与解析（限本地文件，不触网）
- ScraperManager 初始化与适配器构建
- 网络请求通过 mock 避免真实 HTTP
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scraper import (
    AdapterRegistry,
    BaseSourceAdapter,
    ExtractedPaper,
    ExtractedQuestion,
    Fetcher,
    GenericWebAdapter,
    LocalFixtureAdapter,
    ScraperManager,
)


# ===================== AdapterRegistry =====================

class TestAdapterRegistry:
    """适配器注册表。"""

    def test_available_defaults(self):
        available = AdapterRegistry.available()
        assert "local_fixture" in available
        assert "generic_web" in available

    def test_get_existing(self):
        cls = AdapterRegistry.get("local_fixture")
        assert cls is LocalFixtureAdapter

    def test_get_unknown(self):
        cls = AdapterRegistry.get("nonexistent_adapter")
        assert cls is None

    def test_register_new(self):
        class DummyAdapter(BaseSourceAdapter):
            def discover(self, subject_key, year=2026, keyword=""):
                return []
            def fetch_and_parse(self, item, metadata_only=False):
                return None

        AdapterRegistry.register("dummy", DummyAdapter)
        assert "dummy" in AdapterRegistry.available()
        assert AdapterRegistry.get("dummy") is DummyAdapter

    def test_register_overwrite(self):
        class AdapterA(BaseSourceAdapter):
            def discover(self, subject_key, year=2026, keyword=""):
                return []
            def fetch_and_parse(self, item, metadata_only=False):
                return None

        class AdapterB(BaseSourceAdapter):
            def discover(self, subject_key, year=2026, keyword=""):
                return []
            def fetch_and_parse(self, item, metadata_only=False):
                return None

        AdapterRegistry.register("overwrite_test", AdapterA)
        AdapterRegistry.register("overwrite_test", AdapterB)
        assert AdapterRegistry.get("overwrite_test") is AdapterB


# ===================== Fetcher =====================

class TestFetcher:
    """统一网络请求器（mock httpx 避免真实请求）。"""

    @patch("scraper.httpx.Client")
    def test_init_default_ua(self, mock_client):
        """初始化时使用默认 UA 池。"""
        instance = MagicMock()
        mock_client.return_value = instance
        fetcher = Fetcher()
        assert fetcher is not None
        # 验证 client 被初始化
        mock_client.assert_called_once()

    @patch("scraper.httpx.Client")
    def test_fetch_text_success(self, mock_client):
        """fetch_text 成功返回文本。"""
        instance = MagicMock()
        mock_client.return_value = instance
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "test content"
        instance.get.return_value = resp

        fetcher = Fetcher()
        result = fetcher.fetch_text("http://example.com")
        assert result == "test content"

    @patch("scraper.httpx.Client")
    def test_fetch_text_http_error(self, mock_client):
        """fetch_text HTTP 错误返回 None。"""
        instance = MagicMock()
        mock_client.return_value = instance
        resp = MagicMock()
        resp.status_code = 404
        instance.get.return_value = resp

        fetcher = Fetcher()
        result = fetcher.fetch_text("http://example.com/404")
        assert result is None

    @patch("scraper.httpx.Client")
    def test_fetch_text_retry_on_exception(self, mock_client):
        """fetch_text 异常重试后仍失败返回 None。"""
        instance = MagicMock()
        mock_client.return_value = instance
        instance.get.side_effect = Exception("Connection error")

        fetcher = Fetcher()
        result = fetcher.fetch_text("http://example.com")
        assert result is None
        # 应重试多次
        assert instance.get.call_count >= 2

    @patch("scraper.httpx.Client")
    def test_close_does_not_raise(self, mock_client):
        """close 方法不抛异常。"""
        instance = MagicMock()
        mock_client.return_value = instance
        fetcher = Fetcher()
        fetcher.close()  # should not raise


# ===================== BaseSourceAdapter =====================

class TestBaseSourceAdapter:
    """基类工具方法。"""

    @pytest.fixture
    def adapter(self):
        """创建适配器实例供测试实例方法。"""
        return LocalFixtureAdapter({
            "id": "test", "name": "test", "adapter_type": "local_fixture",
        })

    def test_classify_q_type_choice(self, adapter):
        assert adapter._classify_q_type(None, "choice") == "choice"  # None → 回退到 default
        assert adapter._classify_q_type("", "choice") == "choice"  # 空串 → 回退到 default
        assert adapter._classify_q_type("选择题", "solve") == "choice"
        assert adapter._classify_q_type("下列选项中", "solve") == "choice"
        assert adapter._classify_q_type("填空", "solve") == "fill"
        assert adapter._classify_q_type("填入", "solve") == "fill"

    def test_guess_score_with_fallback(self, adapter):
        assert adapter._guess_score("solve", fallback=10.0) == 10.0
        assert adapter._guess_score("choice", fallback=None) == 5.0
        assert adapter._guess_score("fill", fallback=None) == 5.0

    def test_difficulty_tag(self):
        assert BaseSourceAdapter._difficulty_tag(0.8) == "易"
        assert BaseSourceAdapter._difficulty_tag(0.55) == "中"
        assert BaseSourceAdapter._difficulty_tag(0.3) == "难"
        assert BaseSourceAdapter._difficulty_tag(None) == ""


# ===================== LocalFixtureAdapter =====================

class TestLocalFixtureAdapter:
    """本地 fixture 适配器。"""

    FIXTURE_DIR = os.path.join("tests", "fixtures", "papers")

    def test_discover_no_directory(self):
        """不存在的目录返回空列表。"""
        src_cfg = {
            "id": "fx_bad", "name": "bad", "adapter_type": "local_fixture",
            "enabled": True, "base_dir": "/nonexistent/path", "format": "json",
        }
        adapter = LocalFixtureAdapter(src_cfg)
        items = adapter.discover("math", 2026)
        assert items == []

    def test_extract_questions_no_match(self):
        """_extract_questions 无题号时不产生题目。"""
        adapter = LocalFixtureAdapter({
            "id": "test", "name": "test", "adapter_type": "local_fixture",
        })
        questions = adapter._extract_questions("纯文本无题号", "math")
        assert len(questions) == 0

    def test_extract_questions_with_numbers(self):
        """_extract_questions 按题号成功切分。"""
        adapter = LocalFixtureAdapter({
            "id": "test", "name": "test", "adapter_type": "local_fixture",
        })
        text = "1. 第一题内容 答案：A\n2. 第二题内容 答案：B"
        questions = adapter._extract_questions(text, "math")
        assert len(questions) >= 1

    def test_parse_markdown_with_yaml(self):
        """_parse_markdown 正确处理 YAML front-matter。"""
        adapter = LocalFixtureAdapter({
            "id": "test", "name": "test", "adapter_type": "local_fixture",
        })
        # 模拟带 YAML front-matter 的 markdown 文件
        import tempfile
        content = """---
title: Test Paper
subject: math
---
# 数学测试卷

1. 函数 f(x)=x^2 的导数是什么？ 答案：2x
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name
        try:
            paper = adapter._parse_markdown(tmp_path, "math")
            assert paper.title == "数学测试卷"  # 从 # 标题提取
            assert len(paper.questions) >= 1
        finally:
            os.unlink(tmp_path)


# ===================== GenericWebAdapter =====================

class TestGenericWebAdapter:
    """通用网页适配器（mock fetcher 避免真实请求）。"""

    def test_metadata_only_mode(self):
        """metadata_only=True 时仅返回元数据。"""
        adapter = GenericWebAdapter({
            "id": "web_test", "name": "web", "adapter_type": "generic_web",
        })
        item = {"title": "试卷标题", "subject": "math", "year": 2026,
                "url": "http://example.com/paper", "source_id": "web_test",
                "metadata": {"key": "val"}}
        paper = adapter.fetch_and_parse(item, metadata_only=True)
        assert paper is not None
        assert paper.title == "试卷标题"
        assert paper.file_path is None
        assert paper.questions == []

    def test_classify_q_type(self):
        """分类方法集成测试。"""
        adapter = GenericWebAdapter({
            "id": "web_test", "name": "web", "adapter_type": "generic_web",
        })
        assert adapter._classify_q_type("选择题", "solve") == "choice"
        assert adapter._classify_q_type("填空题", "solve") == "fill"


# ===================== ScraperManager =====================

class TestScraperManager:
    """ScraperManager 初始化与适配器构建。"""

    def test_init_with_local_fixture(self):
        """仅用 local_fixture 源初始化不触网。"""
        sources = [{
            "id": "local_fixture",
            "name": "fixture",
            "adapter_type": "local_fixture",
            "enabled": True,
            "base_dir": "tests/fixtures/papers",
            "format": "auto",
        }]
        mgr = ScraperManager(data_sources=sources)
        assert "local_fixture" in mgr._adapters
        assert isinstance(mgr._adapters["local_fixture"], LocalFixtureAdapter)

    def test_init_with_unknown_adapter(self):
        """未知适配器类型静默跳过。"""
        sources = [{
            "id": "unknown_source",
            "name": "unknown",
            "adapter_type": "nonexistent_type",
            "enabled": True,
        }]
        mgr = ScraperManager(data_sources=sources)
        assert len(mgr._adapters) == 0

    def test_init_with_disabled_source(self):
        """禁用源不创建适配器。"""
        sources = [{
            "id": "local_fixture",
            "name": "fixture",
            "adapter_type": "local_fixture",
            "enabled": False,
            "base_dir": "tests/fixtures/papers",
        }]
        mgr = ScraperManager(data_sources=sources)
        assert "local_fixture" not in mgr._adapters

    def test_content_hash_consistency(self):
        """相同输入产生相同哈希。"""
        mgr = ScraperManager(data_sources=[])
        h1 = ScraperManager._content_hash(
            {"title": "卷A", "url": "http://example.com"}, MagicMock(source_id="src1"))
        h2 = ScraperManager._content_hash(
            {"title": "卷A", "url": "http://example.com"}, MagicMock(source_id="src1"))
        assert h1 == h2

    def test_content_hash_different(self):
        """不同输入产生不同哈希。"""
        mgr = ScraperManager(data_sources=[])
        h1 = ScraperManager._content_hash(
            {"title": "卷A", "url": "http://a.com"}, MagicMock(source_id="src1"))
        h2 = ScraperManager._content_hash(
            {"title": "卷B", "url": "http://b.com"}, MagicMock(source_id="src2"))
        assert h1 != h2

    def test_close_does_not_raise(self):
        """close 不抛异常。"""
        import asyncio
        mgr = ScraperManager(data_sources=[])
        asyncio.run(mgr.close())  # should not raise


# ===================== ExtractedPaper/Question =====================

class TestExtractedPaper:
    """ExtractedPaper 数据结构。"""

    def test_to_dict(self):
        paper = ExtractedPaper(
            title="测试卷",
            subject="math",
            year=2026,
            questions=[ExtractedQuestion(q_type="choice", content="题1", score=5.0)],
            total_score=5.0,
        )
        d = paper.to_dict()
        assert d["title"] == "测试卷"
        assert len(d["questions"]) == 1
        assert d["questions"][0]["q_type"] == "choice"
        assert d["questions"][0]["score"] == 5.0

    def test_to_dict_empty_questions(self):
        paper = ExtractedPaper(title="空卷")
        d = paper.to_dict()
        assert d["questions"] == []
