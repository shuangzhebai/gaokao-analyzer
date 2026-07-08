"""数据库后端抽象层测试 — SQLite WAL 模式 + PostgreSQL 降级路径。"""

import pytest

from services.db_service import get_db_backend


class TestDbBackend:
    """数据库后端测试。"""

    @pytest.mark.asyncio
    async def test_sqlite_backend_returns_db_with_methods(self) -> None:
        """SQLite 后端返回的 db 对象应有 execute_fetchone / execute_fetchall。"""
        db = await get_db_backend("sqlite")
        assert hasattr(db, "execute_fetchone")
        assert hasattr(db, "execute_fetchall")
        assert hasattr(db, "execute")
        assert db._backend == "sqlite"
        await db.close()

    @pytest.mark.asyncio
    async def test_sqlite_pragma_are_set(self) -> None:
        """SQLite 连接的 WAL 优化 PRAGMA 应生效。"""
        db = await get_db_backend("sqlite")
        cur = await db.execute("PRAGMA journal_mode")
        row = await cur.fetchone()
        assert row[0] == "wal", f"Expected WAL, got {row[0]}"
        cur = await db.execute("PRAGMA foreign_keys")
        row = await cur.fetchone()
        assert row[0] == 1, "foreign_keys should be ON"
        await db.close()

    @pytest.mark.asyncio
    async def test_fetchone_returns_dict(self) -> None:
        """execute_fetchone 应返回 dict。"""
        db = await get_db_backend("sqlite")
        result = await db.execute_fetchone("SELECT 1 as val")
        assert result is not None
        assert result["val"] == 1
        await db.close()

    @pytest.mark.asyncio
    async def test_fetchall_returns_list_of_dicts(self) -> None:
        """execute_fetchall 应返回 list[dict]。"""
        db = await get_db_backend("sqlite")
        results = await db.execute_fetchall("SELECT 1 as a UNION ALL SELECT 2")
        assert len(results) == 2
        assert results[0]["a"] == 1
        assert results[1]["a"] == 2
        await db.close()
