"""v5.1 SQLite → PostgreSQL 数据迁移工具。

用法：
    python scripts/migrate_to_pg.py --dry-run          # 预览迁移计划
    python scripts/migrate_to_pg.py                    # 执行迁移
    python scripts/migrate_to_pg.py --mode=incremental # 增量模式
    python scripts/migrate_to_pg.py --rollback         # 回滚
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate_to_pg")

# 需要迁移的表（按依赖顺序排列）
TABLES_TO_MIGRATE = [
    "papers",
    "questions",
    "users",
    "reports",
    "analysis_results",
    "question_types",
    "paper_templates",
]

# 迁移记录表
MIGRATION_META_TABLE = "_migration_meta"


async def _connect_sqlite(db_path: str) -> Any:
    """连接 SQLite 源库。"""
    import aiosqlite

    db = await aiosqlite.connect(db_path, timeout=30)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def _connect_pg(dsn: str) -> Any:
    """连接 PostgreSQL 目标库。"""
    import asyncpg

    conn = await asyncpg.connect(dsn)
    return conn


async def _ensure_meta_table(pg: Any) -> None:
    """在 PG 中创建迁移记录表。"""
    await pg.execute(f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_META_TABLE} (
            table_name TEXT PRIMARY KEY,
            last_migrated_at TIMESTAMP,
            row_count INTEGER DEFAULT 0
        )
    """)


async def _get_last_migration(pg: Any, table_name: str) -> str | None:
    """获取某表上次迁移的时间戳。"""
    row = await pg.fetchrow(
        f"SELECT last_migrated_at FROM {MIGRATION_META_TABLE} WHERE table_name = $1",
        table_name
    )
    return row["last_migrated_at"].isoformat() if row and row["last_migrated_at"] else None


async def _record_migration(pg: Any, table_name: str, row_count: int) -> None:
    """记录迁移信息。"""
    now = datetime.utcnow()
    await pg.execute(
        f"""
        INSERT INTO {MIGRATION_META_TABLE} (table_name, last_migrated_at, row_count)
        VALUES ($1, $2, $3)
        ON CONFLICT (table_name)
        DO UPDATE SET last_migrated_at = $2, row_count = $3
        """,
        table_name, now, row_count
    )


async def _table_exists(pg: Any, table_name: str) -> bool:
    """检查 PG 中表是否存在。"""
    row = await pg.fetchrow(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
        table_name
    )
    return row["exists"] if row else False


def _sqlite_type_to_pg(sqlite_type: str) -> str:
    """将 SQLite 数据类型映射到 PostgreSQL。"""
    type_map = {
        "INTEGER": "INTEGER",
        "INT": "INTEGER",
        "REAL": "DOUBLE PRECISION",
        "FLOAT": "DOUBLE PRECISION",
        "TEXT": "TEXT",
        "BLOB": "BYTEA",
        "TIMESTAMP": "TIMESTAMP",
        "BOOLEAN": "BOOLEAN",
    }
    upper = sqlite_type.upper().strip()
    # 处理带括号的类型如 VARCHAR(255)
    base = upper.split("(")[0].strip()
    return type_map.get(base, "TEXT")


def _build_pg_schema(table_name: str, columns_info: list[tuple]) -> str:
    """根据 PRAGMA table_info 输出构建 PG CREATE TABLE 语句。"""
    col_defs: list[str] = []
    for cid, name, col_type, not_null, default_val, pk in columns_info:
        pg_type = _sqlite_type_to_pg(col_type)
        parts = [f'"{name}" {pg_type}']
        if not_null:
            parts.append("NOT NULL")
        if default_val is not None:
            # 处理 SQLite 默认值表达式
            default_str = str(default_val)
            if default_str in ("datetime('now')", "CURRENT_TIMESTAMP"):
                parts.append("DEFAULT CURRENT_TIMESTAMP")
            elif default_str == "''":
                parts.append("DEFAULT ''")
            elif default_str == "'{}'":
                parts.append("DEFAULT '{}'")
            elif default_str == "'[]'":
                parts.append("DEFAULT '[]'")
            else:
                # 尝试数值
                try:
                    float(default_str)
                    parts.append(f"DEFAULT {default_str}")
                except ValueError:
                    parts.append(f"DEFAULT '{default_str}'")
        if pk:
            parts.append("PRIMARY KEY")
            if pg_type == "INTEGER":
                # SQLite INTEGER PRIMARY KEY → PG SERIAL
                parts[0] = f'"{name}" SERIAL'
        col_defs.append(" ".join(parts))
    return f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n    ' + ",\n    ".join(col_defs) + "\n)"


async def _migrate_table(
    sqlite: Any,
    pg: Any,
    table_name: str,
    dry_run: bool = False,
    incremental: bool = False,
) -> int:
    """迁移单个表。"""
    # 获取 SQLite 表结构
    cursor = await sqlite.execute(f"PRAGMA table_info({table_name})")
    columns_info = await cursor.fetchall()

    if not columns_info:
        logger.warning("  表 %s 在 SQLite 中不存在，跳过", table_name)
        return 0

    # 检查 PG 中是否已有表
    exists = await _table_exists(pg, table_name)

    if not exists:
        pg_schema = _build_pg_schema(table_name, columns_info)
        if dry_run:
            logger.info("  将创建 PG 表:\n%s", pg_schema)
        else:
            await pg.execute(pg_schema)
            logger.info("  已在 PG 中创建表 %s", table_name)

    # 查询数据行数
    count_cursor = await sqlite.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_count = (await count_cursor.fetchone())[0]

    if total_count == 0:
        logger.info("  表 %s 为空，跳过数据迁移", table_name)
        if not dry_run:
            await _record_migration(pg, table_name, 0)
        return 0

    # 读取数据
    last_migrated = None
    if incremental and exists:
        last_migrated = await _get_last_migration(pg, table_name)
        if last_migrated:
            where = f"WHERE created_at > '{last_migrated}'" if last_migrated else ""
            count_cursor = await sqlite.execute(
                f"SELECT COUNT(*) FROM {table_name} {where}" if where else
                f"SELECT COUNT(*) FROM {table_name}"
            )
            to_migrate = (await count_cursor.fetchone())[0]
            if to_migrate == 0:
                logger.info("  表 %s 无新增数据，跳过", table_name)
                return 0
            logger.info("  增量迁移 %s 表：上次迁移 %s，本次约 %d 行", table_name, last_migrated, to_migrate)

    if dry_run:
        logger.info("  将迁移 %s 表：%d 行数据", table_name, total_count)
        return total_count

    # 分批读取并写入 PG
    batch_size = 500
    migrated_count = 0
    select_sql = f"SELECT * FROM {table_name}"
    if incremental and last_migrated:
        select_sql += f" WHERE created_at > '{last_migrated}'"
    select_sql += " ORDER BY id"

    cursor = await sqlite.execute(select_sql)
    col_names = [c[1] for c in columns_info]

    while True:
        rows = await cursor.fetchmany(batch_size)
        if not rows:
            break

        for row in rows:
            row_dict = dict(row)
            # 构建 INSERT 语句
            cols = ", ".join(f'"{c}"' for c in col_names)
            placeholders = ", ".join(f"${i+1}" for i in range(len(col_names)))
            values = [row_dict[c] for c in col_names]
            # 将 bytes 转为 str（SQLite 可能存储 TEXT 为字符串）
            clean_values = []
            for v in values:
                if isinstance(v, bytes):
                    clean_values.append(v.decode("utf-8", errors="replace"))
                else:
                    clean_values.append(v)

            try:
                await pg.execute(
                    f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING',
                    *clean_values
                )
            except Exception as e:
                logger.warning("    行 %s 插入失败: %s，跳过", row_dict.get("id"), e)

        migrated_count += len(rows)
        logger.info("  已迁移 %s: %d/%d 行", table_name, migrated_count, total_count)

    # 记录迁移信息
    await _record_migration(pg, table_name, migrated_count)
    logger.info("  ✓ 迁移完成 %s: %d 行", table_name, migrated_count)
    return migrated_count


async def _rollback(pg: Any, dry_run: bool = False) -> None:
    """回滚 PG 中已迁移的表（DROP）。"""
    for table_name in reversed(TABLES_TO_MIGRATE):
        exists = await _table_exists(pg, table_name)
        if exists:
            if dry_run:
                logger.info("  将 DROP 表 %s", table_name)
            else:
                await pg.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
                logger.info("  ✓ 已 DROP 表 %s", table_name)

    # 清理迁移记录表
    meta_exists = await _table_exists(pg, MIGRATION_META_TABLE)
    if meta_exists:
        if dry_run:
            logger.info("  将 DROP 迁移记录表 %s", MIGRATION_META_TABLE)
        else:
            await pg.execute(f'DROP TABLE IF EXISTS {MIGRATION_META_TABLE}')
            logger.info("  ✓ 已 DROP 迁移记录表 %s", MIGRATION_META_TABLE)

    logger.info("回滚完成")


async def main() -> None:
    """主入口。"""
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL 数据迁移工具")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览迁移计划，不实际执行",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="迁移模式：full（全量）/ incremental（增量，仅新增数据）",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚：清理 PG 中已迁移的表",
    )
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="SQLite 数据库路径（默认从 config 读取）",
    )
    args = parser.parse_args()

    # 确定 SQLite 路径
    if args.sqlite_path:
        sqlite_path = args.sqlite_path
    else:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import DB_PATH  # type: ignore[import-untyped]

        sqlite_path = DB_PATH

    # 确定 PG 连接串
    pg_url = os.environ.get("DATABASE_URL", "")
    if not pg_url:
        logger.error("请设置 DATABASE_URL 环境变量指定 PostgreSQL 连接串")
        logger.error("示例: postgresql://gaokao:gaokao@localhost:5432/gaokao")
        sys.exit(1)

    if not os.path.exists(sqlite_path):
        logger.error("SQLite 数据库不存在: %s", sqlite_path)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("SQLite → PostgreSQL 数据迁移工具")
    logger.info("=" * 60)
    logger.info("源库: %s", sqlite_path)
    logger.info("目标: %s", pg_url)
    logger.info("模式: %s", args.mode)
    if args.dry_run:
        logger.info("*** DRY RUN 模式：仅预览，不执行 ***")
    if args.rollback:
        logger.info("*** 回滚模式 ***")
    logger.info("")

    # 连接数据库
    sqlite = await _connect_sqlite(sqlite_path)
    pg = await _connect_pg(pg_url)

    try:
        if args.rollback:
            await _rollback(pg, dry_run=args.dry_run)
            return

        # 确保 PG 迁移记录表存在
        await _ensure_meta_table(pg)

        # 逐个迁移
        total_rows = 0
        for table_name in TABLES_TO_MIGRATE:
            logger.info("正在处理表: %s", table_name)
            rows = await _migrate_table(
                sqlite,
                pg,
                table_name,
                dry_run=args.dry_run,
                incremental=(args.mode == "incremental"),
            )
            total_rows += rows

        logger.info("")
        logger.info("=" * 60)
        if args.dry_run:
            logger.info("DRY RUN 完成，预计迁移 %d 行数据（%d 张表）", total_rows, len(TABLES_TO_MIGRATE))
        else:
            logger.info("迁移完成！共迁移 %d 行数据（%d 张表）", total_rows, len(TABLES_TO_MIGRATE))

    finally:
        await sqlite.close()
        await pg.close()


if __name__ == "__main__":
    asyncio.run(main())
