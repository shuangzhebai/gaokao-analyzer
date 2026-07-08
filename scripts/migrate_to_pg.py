"""
SQLite → PostgreSQL 数据迁移脚本。
用法: .venv/Scripts/python scripts/migrate_to_pg.py

要求: PostgreSQL 已运行（docker compose up -d postgres），环境变量 GAOKAO_DB=postgresql
"""

import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate")

# 加入项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PATH
from models import run_migrations


# SQLite 到 PostgreSQL 的类型映射
TYPE_MAP = {
    "INTEGER": "INTEGER",
    "TEXT": "TEXT",
    "REAL": "DOUBLE PRECISION",
    "BLOB": "BYTEA",
    "NUMERIC": "NUMERIC",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "BOOLEAN",
}

# 迁移顺序（依赖关系：先无外键依赖的表）
TABLE_ORDER = [
    "subjects",
    "roles",
    "users",
    "user_roles",
    "papers",
    "questions",
    "paper_reports",
    "analysis_results",
    "knowledge_points",
    "audit_log",
    "schema_migrations",
    "papers_fts",
]


def _convert_ddl(sqlite_schema: str, table_name: str) -> str:
    """将 SQLite CREATE TABLE 语句转换为 PostgreSQL 兼容语法。"""
    pg = sqlite_schema.replace("AUTOINCREMENT", "").replace("autoincrement", "")
    pg = pg.replace("`", '"')
    # INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
    pg = pg.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
    pg = pg.replace("INTEGER  PRIMARY KEY", "SERIAL PRIMARY KEY")
    # TEXT 默认值去掉单引号转义差异
    for old, new in TYPE_MAP.items():
        pg = pg.replace(f" {old}", f" {new}")
    # 去掉 sqlite-specific
    pg = pg.replace(" WITHOUT ROWID", "")
    return pg


async def _get_sqlite_schema(sqlite_db) -> dict[str, str]:
    """读取 SQLite 中所有表的建表语句。"""
    schemas = {}
    cursor = await sqlite_db.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'papers_fts%'"
    )
    rows = await cursor.fetchall()
    for name, sql in rows:
        schemas[name] = sql
    return schemas


async def _get_pg_schema(pg_conn) -> set[str]:
    """读取 PostgreSQL 中已存在的表。"""
    rows = await pg_conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )
    return {r["tablename"] for r in rows}


async def migrate() -> None:
    """主迁移流程。"""
    import aiosqlite
    import asyncpg

    pg_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://gaokao:gaokao@localhost:5432/gaokao",
    )

    logger.info("=" * 60)
    logger.info("SQLite → PostgreSQL 数据迁移")
    logger.info("=" * 60)
    logger.info("源数据库: %s", DB_PATH)
    logger.info("目标数据库: %s", pg_url)

    # 1. 连接 SQLite
    logger.info("\n[1/5] 连接 SQLite...")
    sqlite_db = await aiosqlite.connect(DB_PATH)
    sqlite_db.row_factory = aiosqlite.Row

    # 2. 读取 SQLite schema
    logger.info("[2/5] 读取 SQLite 表结构...")
    schemas = await _get_sqlite_schema(sqlite_db)
    logger.info("  发现 %d 张数据表", len(schemas))
    for name in schemas:
        logger.info("    - %s", name)

    # 3. 连接 PostgreSQL
    logger.info("[3/5] 连接 PostgreSQL...")
    try:
        pg_conn = await asyncpg.connect(pg_url)
        logger.info("  连接成功")
    except Exception as e:
        logger.error("  连接失败: %s", e)
        logger.error("  请确认 PostgreSQL 已启动: docker compose up -d postgres")
        sys.exit(1)

    try:
        # 4. 迁移 schema
        logger.info("[4/5] 迁移表结构...")
        existing_tables = await _get_pg_schema(pg_conn)
        tables_created = 0

        for table_name in TABLE_ORDER:
            if table_name not in schemas:
                continue
            if table_name in existing_tables:
                logger.info("  表已存在，跳过: %s", table_name)
                continue

            ddl = _convert_ddl(schemas[table_name], table_name)
            # 去除 fts 虚拟表
            if "fts" in table_name.lower():
                continue
            try:
                await pg_conn.execute(ddl)
                logger.info("  已创建: %s", table_name)
                tables_created += 1
            except Exception as e:
                logger.warning("  创建表 %s 失败: %s", table_name, e)

        logger.info("  新创建 %d 张表", tables_created)

        # 5. 迁移数据
        logger.info("[5/5] 迁移数据...")
        total_rows = 0
        for table_name in TABLE_ORDER:
            if table_name not in schemas:
                continue
            if "fts" in table_name.lower():
                continue

            # 读取 SQLite 数据
            rows = await sqlite_db.execute_fetchall(f"SELECT * FROM {table_name}")
            if not rows:
                logger.info("  跳过空表: %s", table_name)
                continue

            # 构建 INSERT
            columns = list(rows[0].keys())
            placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
            col_names = ", ".join(columns)
            insert_sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

            # 批量写入 PG
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                try:
                    await pg_conn.executemany(insert_sql, [list(r.values()) for r in batch])
                except Exception as e:
                    logger.warning("  %s: 批次 %d 写入失败: %s", table_name, i // batch_size, e)

            total_rows += len(rows)
            logger.info("  %s: %d 行", table_name, len(rows))

        logger.info("\n迁移完成！")
        logger.info("  表数量: %d", len(schemas))
        logger.info("  行总数: %d", total_rows)

        # 运行 PG 迁移
        logger.info("运行 PostgreSQL 迁移...")
        await run_migrations(pg_conn)
        logger.info("迁移已应用")

    finally:
        await pg_conn.close()
    await sqlite_db.close()


if __name__ == "__main__":
    asyncio.run(migrate())
