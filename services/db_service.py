"""
数据库后端抽象层 — 统一 SQLite (aiosqlite) 和 PostgreSQL (asyncpg) 接口。

所有 repository 通过 execute/execute_fetchone/execute_fetchall/commit/close 五个方法操作，
不依赖具体数据库实现。数据库切换只需改 config.py 一行配置。
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("gaokao")

# ============ 全局连接池 ============
_sqlite_pool: dict[str, Any] = {}  # SQLite 连接（aiosqlite 无池概念，用 dict 跟踪）
_pg_pool: Any = None  # PostgreSQL 连接池（asyncpg 原生池）


async def get_db_backend(db_type: str = "") -> Any:
    """获取数据库连接（自动选择后端）。

    Args:
        db_type: "sqlite" | "postgresql" | "" (从环境变量 GAOKAO_DB 读取)

    数据库切换：
        - 设置环境变量 GAOKAO_DB=postgresql 使用 PostgreSQL
        - 设置环境变量 GAOKAO_DB=sqlite 使用 SQLite（默认）
    PostgreSQL 连接池大小：
        - PG_POOL_MIN_SIZE 环境变量（默认 2）
        - PG_POOL_MAX_SIZE 环境变量（默认 10）
    """
    global _pg_pool
    if not db_type:
        db_type = os.environ.get("GAOKAO_DB", "sqlite").lower()

    if db_type == "postgresql":
        return await _connect_pg()
    return await _connect_sqlite()


async def _connect_sqlite() -> Any:
    """连接 SQLite（WAL 模式，极致优化参数）。"""
    import aiosqlite
    from config import DB_PATH

    db = await aiosqlite.connect(DB_PATH, timeout=30)
    db.row_factory = aiosqlite.Row

    # WAL 模式 + 性能优化 PRAGMA
    for pragma, val in (
        ("journal_mode", "WAL"),
        ("synchronous", "NORMAL"),
        ("cache_size", -8000),
        ("busy_timeout", 10000),
        ("foreign_keys", "ON"),
        ("temp_store", "MEMORY"),
        ("mmap_size", 268435456),
    ):
        await db.execute(f"PRAGMA {pragma}={val}")

    # 注入快捷方法
    _orig_exec = db.execute

    async def fetchone(sql: str, params: Optional[list[Any]] = None) -> Optional[dict[str, Any]]:
        cur = await _orig_exec(sql, params or [])
        row = await cur.fetchone()
        return dict(row) if row else None

    async def fetchall(sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
        cur = await _orig_exec(sql, params or [])
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    db.execute_fetchone = fetchone  # type: ignore[attr-defined]
    db.execute_fetchall = fetchall  # type: ignore[attr-defined]
    db._backend = "sqlite"  # type: ignore[attr-defined]
    return db


async def _connect_pg() -> Any:
    """连接 PostgreSQL（连接池，池大小可从环境变量配置）。"""
    global _pg_pool
    import asyncpg

    pg_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://gaokao:gaokao@localhost:5432/gaokao",
    )
    # 从环境变量读取连接池大小（允许运行时调整）
    pool_min_size = int(os.environ.get("PG_POOL_MIN_SIZE", "2"))
    pool_max_size = int(os.environ.get("PG_POOL_MAX_SIZE", "10"))
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            pg_url,
            min_size=pool_min_size,
            max_size=pool_max_size,
            command_timeout=30,
        )
        logger.info(
            "PostgreSQL 连接池已创建 (min_size=%d, max_size=%d, url=%s)",
            pool_min_size, pool_max_size, pg_url,
        )

    conn = await _pg_pool.acquire()

    # 包装 asyncpg.Connection 为统一接口
    orig_execute = conn.execute

    async def fetchone(sql: str, params: Optional[list[Any]] = None) -> Optional[dict[str, Any]]:
        if params is None:
            params = []
        # asyncpg 用 $1 参数占位符，但这里保持 ? 兼容 SQLite
        # 注意：实际使用中 PG 的 SQL 需用 $1 语法或 psycopg2 风格
        # 此处假设调用方提供了正确格式的 SQL
        row = await conn.fetchrow(sql, *params)
        return dict(row) if row else None

    async def fetchall(sql: str, params: Optional[list[Any]] = None) -> list[dict[str, Any]]:
        if params is None:
            params = []
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    conn.execute_fetchone = fetchone  # type: ignore[attr-defined]
    conn.execute_fetchall = fetchall  # type: ignore[attr-defined]
    conn._backend = "postgresql"  # type: ignore[attr-defined]
    conn._pool = _pg_pool  # type: ignore[attr-defined] — 用于释放
    return conn


async def close_db(db: Any) -> None:
    """关闭数据库连接。"""
    backend = getattr(db, "_backend", "sqlite")
    if backend == "postgresql":
        pool = getattr(db, "_pool", None)
        if pool:
            await pool.release(db)
    else:
        await db.close()


async def close_all() -> None:
    """关闭全局连接池（lifespan shutdown 时调用）。"""
    global _pg_pool, _sqlite_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
        logger.info("PostgreSQL 连接池已关闭")
