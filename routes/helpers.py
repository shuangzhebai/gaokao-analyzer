"""数据库连接帮助函数 — v7.2 新增

消除所有路由文件中重复的 get_db() 样板代码。
提供可复用的 async context manager。
"""
from typing import AsyncGenerator, Any
from contextlib import asynccontextmanager


class DbSession:
    """数据库会话封装 — 自动管理连接生命周期"""
    _db = None

    @classmethod
    async def get(cls):
        """懒加载获取数据库连接"""
        if cls._db is None:
            from models import get_db
            db_gen = get_db()
            cls._db = await db_gen.__anext__()
        return cls._db

    @classmethod
    async def close(cls):
        if cls._db is not None:
            try:
                await cls._db.close()
            except Exception:
                pass
            cls._db = None

    @classmethod
    async def execute(cls, sql: str, params: tuple = ()):
        db = await cls.get()
        return await db.execute(sql, params)

    @classmethod
    async def fetchone(cls, sql: str, params: tuple = ()):
        cursor = await cls.execute(sql, params)
        return await cursor.fetchone()

    @classmethod
    async def fetchall(cls, sql: str, params: tuple = ()):
        cursor = await cls.execute(sql, params)
        return await cursor.fetchall()

    @classmethod
    async def commit(cls):
        db = await cls.get()
        await db.commit()


# 简便的单函数接口
async def db_one(sql: str, *params) -> dict | None:
    """执行查询并返回一条结果"""
    cursor = await DbSession.execute(sql, params)
    return await cursor.fetchone()


async def db_all(sql: str, *params) -> list[dict]:
    """执行查询并返回全部结果"""
    cursor = await DbSession.execute(sql, params)
    return await cursor.fetchall()


async def db_exec(sql: str, *params) -> int:
    """执行写入操作，返回影响行数"""
    cursor = await DbSession.execute(sql, params)
    await DbSession.commit()
    return cursor.rowcount if hasattr(cursor, 'rowcount') else 0


async def db_insert(sql: str, *params) -> int:
    """执行插入，返回 lastrowid"""
    cursor = await DbSession.execute(sql, params)
    await DbSession.commit()
    return cursor.lastrowid if hasattr(cursor, 'lastrowid') else 0
