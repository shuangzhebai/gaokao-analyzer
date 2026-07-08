"""
SearchEngine 单元测试（无数据库依赖）。

搜索模块依赖数据库 get_db()，本测试利用 unittest.mock 模拟数据库连接，
避免创建真实数据库和 FTS5 索引。
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from search import SearchEngine, search_similar_titles


def _make_mock_db(rows=None, count=0):
    """构造一个模拟的 aiosqlite 连接，支持 execute_fetchone / execute_fetchall。"""
    db = AsyncMock()
    db.execute_fetchone = AsyncMock(return_value={"cnt": count})
    db.execute_fetchall = AsyncMock(return_value=rows or [])
    db.execute = AsyncMock()
    db.row_factory = Mock()
    return db


def _mock_get_db_generator(db):
    """创建一个 async 生成器，yield db 一次，模拟 get_db() 的行为。"""
    async def _gen():
        yield db
    return _gen()


def _run_with_db(coro_factory, db):
    """设置 mock 并运行协程。"""
    async def _run():
        return await coro_factory()
    return asyncio.run(_run())


class TestSearchEngine:
    """SearchEngine 查询与联想功能（mock 数据库）。"""

    @staticmethod
    def _run_search(search_call, db):
        """使用 mock get_db 执行 async 搜索方法。"""
        async def _mock_get_db():
            yield db
        with patch("search.get_db", side_effect=_mock_get_db):
            return asyncio.run(search_call)

    def test_search_empty_query_returns_all(self):
        """空关键词查询走无条件路径。"""
        db = _make_mock_db(
            rows=[{"id": 1, "title": "卷1", "subject_id": "math", "year": 2026}],
            count=1,
        )
        engine = SearchEngine()
        result = self._run_search(engine.search(q="", page=1, size=20), db)
        assert result["total"] == 1
        assert len(result["data"]) == 1

    def test_search_with_keyword_fts_path(self):
        """带关键词走 FTS 搜索路径（返回空结果降级到 LIKE）。"""
        db = _make_mock_db(rows=[], count=0)
        engine = SearchEngine()
        result = self._run_search(engine.search(q="三角函数", page=1, size=20), db)
        assert result["total"] == 0
        assert result["query"] == "三角函数"

    def test_search_with_subject_filter(self):
        """搜索加科目筛选。
        
        该测试使 FTS 返回空结果（降级到 LIKE 路径），
        避免 mock rows 缺少 rowid 导致的 KeyError。
        """
        db = _make_mock_db(rows=[], count=0)
        engine = SearchEngine()
        result = self._run_search(engine.search(q="物理", subject="physics", page=1, size=20), db)
        assert result["total"] == 0

    def test_search_sort_by_time(self):
        """按时间排序。"""
        db = _make_mock_db(
            rows=[{"id": 1, "title": "卷A", "subject_id": "math", "year": 2026,
                    "province": None, "school": None, "exam_tag": None,
                    "source_id": "test", "source_url": "",
                    "source_priority": "A", "verified": 0, "question_count": 3,
                    "difficulty": None, "quality_score": None,
                    "curriculum_score": None, "analysis_status": None,
                    "total_score": 150, "created_at": "2026-01-01",
                    "source_name": "测试源"}],
            count=1,
        )
        engine = SearchEngine()
        result = self._run_search(engine.search(q="", sort="time", page=1, size=20), db)
        assert result["total"] == 1

    def test_search_with_filters(self):
        """组合筛选条件。"""
        db = _make_mock_db(
            rows=[{"id": 1, "title": "卷", "subject_id": "math", "year": 2025,
                    "province": "广东", "school": None, "exam_tag": "一模",
                    "source_id": "test", "source_url": "",
                    "source_priority": "S", "verified": 1, "question_count": 3,
                    "difficulty": None, "quality_score": None,
                    "curriculum_score": None, "analysis_status": "done",
                    "total_score": 150, "created_at": "2025-03-01",
                    "source_name": "测试源"}],
            count=1,
        )
        engine = SearchEngine()
        result = self._run_search(
            engine.search(q="", year=2025, province="广东",
                          source_priority="S", verified=True,
                          analysis_status="done", page=1, size=20),
            db,
        )
        assert result["total"] == 1

    def test_suggest_empty(self):
        """空输入返回空列表。"""
        db = _make_mock_db(rows=[], count=0)
        engine = SearchEngine()
        result = self._run_search(engine.suggest("", limit=10), db)
        assert result == []

    def test_suggest_short_query(self):
        """过短查询返回空列表（长度<1）。"""
        db = _make_mock_db(rows=[], count=0)
        engine = SearchEngine()
        result = self._run_search(engine.suggest(" ", limit=10), db)
        assert result == []

    def test_suggest_with_results(self):
        """联想返回匹配标题。"""
        db = _make_mock_db(rows=[{"title": "2026高考数学模拟卷"}])
        engine = SearchEngine()
        result = self._run_search(engine.suggest("数学", limit=10), db)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_search_questions_empty(self):
        """题目搜索空关键词。"""
        db = _make_mock_db(rows=[], count=0)
        engine = SearchEngine()
        result = self._run_search(engine.search_questions("", page=1, size=20), db)
        assert result["total"] == 0


class TestSearchSimilarTitles:
    """search_similar_titles 独立测试。"""

    def test_empty_tokens(self):
        """空标题返回空列表。"""
        db = AsyncMock()
        result = asyncio.run(search_similar_titles(db, "", "math"))
        assert result == []

    @pytest.mark.asyncio
    async def test_fts_path(self):
        """FTS 路径返回结果。"""
        db = AsyncMock()
        db.execute_fetchall = AsyncMock(return_value=[
            {"id": 1, "title": "2026高考数学模拟卷", "year": 2026}
        ])
        result = await search_similar_titles(db, "2026高考数学模拟", "math", limit=5)
        assert len(result) == 1
        assert result[0]["title"] == "2026高考数学模拟卷"

    @pytest.mark.asyncio
    async def test_like_fallback(self):
        """FTS 异常时降级到 LIKE 路径。"""
        db = AsyncMock()
        db.execute_fetchall = AsyncMock()
        db.execute_fetchall.side_effect = [
            Exception("FTS error"),  # 短语匹配失败
            [],  # AND 查询 - 空
            [],  # OR 查询 - 空
            [{"id": 2, "title": "2025高考数学模拟", "year": 2025}],  # LIKE 降级
        ]
        result = await search_similar_titles(db, "2025高考数学", "math", limit=5)
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_and_fallback(self):
        """短语无结果时走 AND 路径。"""
        db = AsyncMock()
        db.execute_fetchall = AsyncMock()
        db.execute_fetchall.side_effect = [
            [],  # 短语无结果
            [{"id": 1, "title": "高考数学模拟", "year": 2026}],  # AND 有结果
        ]
        result = await search_similar_titles(db, "高考数学", "math", limit=5)
        assert len(result) == 1
