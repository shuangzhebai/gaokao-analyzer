"""
数据库模型 v5.1 - SQLite + aiosqlite + FTS5
v5.1: 新增 official_docs、verification_audit 表；引入 schema_migrations 版本化迁移
"""
import aiosqlite
import logging
from typing import Any

from config import DB_PATH

logger = logging.getLogger("gaokao")


# ============ 版本化迁移（T01：防清空数据） ============

# 当前 schema 版本号。升级时请递增本常量并在 MIGRATIONS 中注册对应迁移函数。
CURRENT_SCHEMA_VERSION = 3


async def _ensure_schema_migrations(db: Any) -> None:
    """确保迁移记录表存在。"""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               description TEXT
           )"""
    )


async def _get_applied_version(db: Any) -> int:
    """读取已应用的最高 schema 版本（无记录返回 0）。"""
    try:
        row = await db.execute_fetchone("SELECT MAX(version) AS v FROM schema_migrations")
        return int(row["v"]) if row and row["v"] is not None else 0
    except Exception:  # noqa: BLE001
        return 0


async def _add_column_if_missing(db: Any, table: str, column: str, definition: str) -> None:
    """若表中缺少某列，则增量 ALTER 添加（幂等，不删库、不丢数据）。"""
    cursor = await db.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in await cursor.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def _migrate_to_v1(db: Any) -> None:
    """基线迁移 v1（v5.1）。

    对已有旧版（v4.x）数据库补齐 v5.x 新增列；新库已由 SCHEMA 的
    CREATE IF NOT EXISTS 直接建好，此处为幂等补齐，不会清空任何数据。
    """
    # papers 表 v5.x 新增列
    await _add_column_if_missing(db, "papers", "content_hash", "TEXT")
    await _add_column_if_missing(db, "papers", "duplicate_of", "INTEGER")
    await _add_column_if_missing(db, "papers", "dedup_status", "TEXT DEFAULT 'unique'")
    await _add_column_if_missing(db, "papers", "source_priority", "TEXT DEFAULT 'B'")
    await _add_column_if_missing(db, "papers", "collected_at", "TIMESTAMP")
    await _add_column_if_missing(db, "papers", "collector", "TEXT DEFAULT 'system'")
    await _add_column_if_missing(db, "papers", "verified", "INTEGER DEFAULT 0")
    await _add_column_if_missing(db, "papers", "question_count", "INTEGER DEFAULT 0")
    await _add_column_if_missing(db, "papers", "explanation", "TEXT")
    await _add_column_if_missing(db, "papers", "difficulty_tag", "TEXT")
    # questions 表 v5.x 新增列
    await _add_column_if_missing(db, "questions", "content_hash", "TEXT")
    await _add_column_if_missing(db, "questions", "similar_to", "INTEGER")


async def _migrate_to_v2(db: Any) -> None:
    """阶段二迁移 v2：新增 paper_reports 表（报告落库，便于查询），幂等。"""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS paper_reports (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               paper_id INTEGER NOT NULL,
               report_json TEXT,
               composite_score REAL,
               grade TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
           )"""
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_paper_reports_paper ON paper_reports(paper_id)"
    )


async def _migrate_to_v3(db: Any) -> None:
    """阶段三迁移 v3：新增 audit_log 操作审计日志表，幂等。"""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL DEFAULT 'anonymous',
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            ip_address TEXT,
            user_agent TEXT,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user)")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id)"
    )
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")


# 版本号 -> (描述, 迁移函数)。后续升级只需追加更高版本号即可。
MIGRATIONS = {
    1: ("v5.1 baseline: 补齐 v5.x 字段与迁移表", _migrate_to_v1),
    2: ("phase2: 新增 paper_reports 报告表", _migrate_to_v2),
    3: ("phase3: 新增 audit_log 操作审计日志表", _migrate_to_v3),
}


async def run_migrations(db: Any) -> None:
    """按版本号增量应用迁移，绝不删除数据库。

    迁移失败会抛出 RuntimeError 并提示用户手动备份重建（而非自动清库）。
    """
    await _ensure_schema_migrations(db)
    current = await _get_applied_version(db)
    if current >= CURRENT_SCHEMA_VERSION:
        return
    for ver in range(current + 1, CURRENT_SCHEMA_VERSION + 1):
        desc, fn = MIGRATIONS.get(ver, (f"migration to v{ver}", None))
        try:
            if fn is not None:
                await fn(db)
            await db.execute(
                "INSERT OR REPLACE INTO schema_migrations (version, description) VALUES (?, ?)",
                (ver, desc),
            )
            await db.commit()
            logger.info(f"DB migration applied: v{ver} - {desc}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"DB migration v{ver} failed: {e}")
            raise RuntimeError(
                f"数据库 schema 迁移失败 (目标 v{ver}): {e}。"
                f"请先备份 data/gaokao.db，再手动重建；不要使用 --reset 以免数据清空。"
            ) from e


async def init_db() -> None:
    """初始化所有数据表 + FTS5 索引 + 版本化迁移"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await run_migrations(db)
        await db.commit()


from collections.abc import AsyncGenerator


async def get_db() -> AsyncGenerator[Any, None]:
    """获取数据库连接，添加 execute_fetchone / execute_fetchall 包装方法"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row

    _orig_execute = db.execute

    async def _execute_fetchone(sql: str, params: Any = None) -> dict[str, Any] | None:
        cursor = await _orig_execute(sql, params or [])
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def _execute_fetchall(sql: str, params: Any = None) -> list[dict[str, Any]]:
        cursor = await _orig_execute(sql, params or [])
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    db.execute_fetchone = _execute_fetchone  # type: ignore[attr-defined]
    db.execute_fetchall = _execute_fetchall  # type: ignore[assignment]

    try:
        yield db
    finally:
        await db.close()


SCHEMA = """
-- 科目表
CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    total_score INTEGER NOT NULL DEFAULT 150,
    time_min INTEGER NOT NULL DEFAULT 120
);

-- 数据源表（增强：增加描述和频率限制）
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT,
    priority TEXT NOT NULL DEFAULT 'B',
    enabled INTEGER NOT NULL DEFAULT 1,
    rate_limit INTEGER DEFAULT 3,
    description TEXT
);

-- 试卷表（v4.0 重设计：增加来源追溯、查重标记）
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    paper_type TEXT NOT NULL,
    year INTEGER NOT NULL DEFAULT 2026,
    province TEXT,
    school TEXT,
    exam_tag TEXT,

    -- 来源追溯
    source_id TEXT,
    source_url TEXT,
    source_priority TEXT DEFAULT 'B',
    collected_at TIMESTAMP,
    collector TEXT DEFAULT 'system',
    verified INTEGER DEFAULT 0,
    verified_at TIMESTAMP,

    -- 内容
    file_path TEXT,
    total_score REAL DEFAULT 150,
    difficulty REAL,
    question_count INTEGER DEFAULT 0,

    -- 分析结果
    quality_score REAL,
    curriculum_score REAL,
    analysis_status TEXT DEFAULT 'pending',
    curriculum_json TEXT,
    quality_json TEXT,
    simulation_json TEXT,

    -- 去重标记
    content_hash TEXT,
    duplicate_of INTEGER,
    dedup_status TEXT DEFAULT 'unique',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (duplicate_of) REFERENCES papers(id)
);

-- 题目表（v4.0 增强：解析字段、难度标签、内容哈希）
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    q_number INTEGER NOT NULL,
    q_type TEXT NOT NULL,
    content TEXT,
    options TEXT,
    answer TEXT,
    explanation TEXT,
    score REAL NOT NULL DEFAULT 0,
    knowledge_points TEXT,
    difficulty_tag TEXT,

    -- IRT 参数
    irt_a REAL,
    irt_b REAL,
    irt_c REAL DEFAULT 0.0,
    discrimination REAL,

    -- 课标与质量
    cognitive_level TEXT,
    core_competency TEXT,
    quality_rating TEXT,
    is_quality INTEGER DEFAULT 0,

    -- 去重
    content_hash TEXT,
    similar_to INTEGER,

    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- 知识点表
CREATE TABLE IF NOT EXISTS knowledge_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    parent_id INTEGER,
    level INTEGER NOT NULL DEFAULT 1,
    weight REAL DEFAULT 1.0,
    description TEXT,
    cognitive_requirement TEXT,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (parent_id) REFERENCES knowledge_points(id)
);

-- 分析结果表
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    ref_paper_id INTEGER,
    fit_score REAL,
    knowledge_coverage TEXT,
    difficulty_ks_stat REAL,
    difficulty_ks_pvalue REAL,
    question_type_match TEXT,
    quality_score REAL,
    curriculum_alignment REAL,
    simulation_mean REAL,
    simulation_std REAL,
    simulation_median REAL,
    simulation_json TEXT,
    score_distribution_json TEXT,
    analysis_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (ref_paper_id) REFERENCES papers(id)
);

-- 爬取日志表（v4.0 增强：去重结果、响应时间）
CREATE TABLE IF NOT EXISTS scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    url TEXT,
    status TEXT NOT NULL,
    error_msg TEXT,
    paper_id INTEGER,
    dedup_result TEXT,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 去重记录表（v4.0 新增）
CREATE TABLE IF NOT EXISTS dedup_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id_1 INTEGER NOT NULL,
    paper_id_2 INTEGER NOT NULL,
    similarity REAL NOT NULL,
    method TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id_1) REFERENCES papers(id),
    FOREIGN KEY (paper_id_2) REFERENCES papers(id)
);

-- FTS5 试卷全文搜索索引
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title,
    province,
    school,
    exam_tag,
    content='papers',
    content_rowid='id'
);

-- FTS5 题目全文搜索索引
CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(
    content,
    knowledge_points,
    content='questions',
    content_rowid='id'
);

-- FTS 同步触发器：试卷插入后同步到 FTS
CREATE TRIGGER IF NOT EXISTS papers_fts_insert AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, province, school, exam_tag)
    VALUES (new.id, new.title, new.province, new.school, new.exam_tag);
END;

CREATE TRIGGER IF NOT EXISTS papers_fts_update AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, province, school, exam_tag)
    VALUES ('delete', old.id, old.title, old.province, old.school, old.exam_tag);
    INSERT INTO papers_fts(rowid, title, province, school, exam_tag)
    VALUES (new.id, new.title, new.province, new.school, new.exam_tag);
END;

CREATE TRIGGER IF NOT EXISTS papers_fts_delete AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, province, school, exam_tag)
    VALUES ('delete', old.id, old.title, old.province, old.school, old.exam_tag);
END;

-- FTS 同步触发器：题目插入后同步到 FTS
CREATE TRIGGER IF NOT EXISTS questions_fts_insert AFTER INSERT ON questions BEGIN
    INSERT INTO questions_fts(rowid, content, knowledge_points)
    VALUES (new.id, new.content, new.knowledge_points);
END;

CREATE TRIGGER IF NOT EXISTS questions_fts_update AFTER UPDATE ON questions BEGIN
    INSERT INTO questions_fts(questions_fts, rowid, content, knowledge_points)
    VALUES ('delete', old.id, old.content, old.knowledge_points);
    INSERT INTO questions_fts(rowid, content, knowledge_points)
    VALUES (new.id, new.content, new.knowledge_points);
END;

CREATE TRIGGER IF NOT EXISTS questions_fts_delete AFTER DELETE ON questions BEGIN
    INSERT INTO questions_fts(questions_fts, rowid, content, knowledge_points)
    VALUES ('delete', old.id, old.content, old.knowledge_points);
END;

-- 索引
CREATE INDEX IF NOT EXISTS idx_papers_subject ON papers(subject_id);
CREATE INDEX IF NOT EXISTS idx_papers_type ON papers(paper_type);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_province ON papers(province);
CREATE INDEX IF NOT EXISTS idx_papers_source_priority ON papers(source_priority);
CREATE INDEX IF NOT EXISTS idx_papers_content_hash ON papers(content_hash);
CREATE INDEX IF NOT EXISTS idx_papers_dedup ON papers(dedup_status);
CREATE INDEX IF NOT EXISTS idx_papers_exam_tag ON papers(exam_tag);
CREATE INDEX IF NOT EXISTS idx_papers_composite ON papers(subject_id, year, paper_type);
CREATE INDEX IF NOT EXISTS idx_questions_paper ON questions(paper_id);
CREATE INDEX IF NOT EXISTS idx_questions_quality ON questions(is_quality);
CREATE INDEX IF NOT EXISTS idx_questions_hash ON questions(content_hash);
CREATE INDEX IF NOT EXISTS idx_kp_subject ON knowledge_points(subject_id);
CREATE INDEX IF NOT EXISTS idx_analysis_paper ON analysis_results(paper_id);
CREATE INDEX IF NOT EXISTS idx_scrape_status ON scrape_logs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_dedup_papers ON dedup_records(paper_id_1, paper_id_2);

-- v5.0: 官方文件库表
CREATE TABLE IF NOT EXISTS official_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    priority TEXT NOT NULL DEFAULT 'S',
    year INTEGER,
    summary TEXT,
    content TEXT,
    file_path TEXT,
    content_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- v5.0: 真实性审核记录表
CREATE TABLE IF NOT EXISTS verification_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    audit_type TEXT NOT NULL DEFAULT 'full',
    score INTEGER DEFAULT 100,
    grade TEXT DEFAULT 'A',
    status TEXT DEFAULT 'verified',
    issues_json TEXT,
    audited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auditor TEXT DEFAULT 'system',
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- v5.0 索引
CREATE INDEX IF NOT EXISTS idx_official_docs_category ON official_docs(category);
CREATE INDEX IF NOT EXISTS idx_official_docs_source ON official_docs(source);
CREATE INDEX IF NOT EXISTS idx_official_docs_year ON official_docs(year);
CREATE INDEX IF NOT EXISTS idx_verification_paper ON verification_audit(paper_id);
CREATE INDEX IF NOT EXISTS idx_verification_grade ON verification_audit(grade);

-- v5.1: 版本化迁移记录表（防清空数据，增量 ALTER 不删库）
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 阶段二：试卷分析报告表（独立表，便于查询；不污染 papers 主表）
CREATE TABLE IF NOT EXISTS paper_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    report_json TEXT,
    composite_score REAL,
    grade TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_paper_reports_paper ON paper_reports(paper_id);

-- v3: 操作审计日志（与 verification_audit 试卷真实性审核完全独立）
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL DEFAULT 'anonymous',
    action TEXT NOT NULL,            -- POST / PUT / DELETE
    resource_type TEXT NOT NULL,     -- 'paper', 'question', 'analysis', 'user', etc.
    resource_id TEXT,                -- 被操作资源的 ID（字符串兼容）
    ip_address TEXT,
    user_agent TEXT,
    detail TEXT,                     -- JSON 格式额外上下文
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
"""


# 新课标九科知识点种子数据
KNOWLEDGE_SEED = {
    "chinese": [
        ("1.1", "语言文字运用", None, 1),
        ("1.1.1", "现代汉语读音", "1.1", 2),
        ("1.1.2", "现代汉语字形", "1.1", 2),
        ("1.1.3", "词语运用", "1.1", 2),
        ("1.1.4", "病句辨析", "1.1", 2),
        ("1.1.5", "修辞手法", "1.1", 2),
        ("1.1.6", "语言连贯", "1.1", 2),
        ("1.2", "古代诗文阅读", None, 1),
        ("1.2.1", "文言文阅读", "1.2", 2),
        ("1.2.2", "古代诗歌鉴赏", "1.2", 2),
        ("1.2.3", "名篇名句默写", "1.2", 2),
        ("1.3", "现代文阅读", None, 1),
        ("1.3.1", "论述类文本阅读", "1.3", 2),
        ("1.3.2", "文学类文本阅读", "1.3", 2),
        ("1.3.3", "实用类文本阅读", "1.3", 2),
        ("1.4", "写作", None, 1),
        ("1.4.1", "材料作文", "1.4", 2),
        ("1.4.2", "命题作文", "1.4", 2),
        ("1.4.3", "任务驱动型作文", "1.4", 2),
    ],
    "math": [
        ("2.1", "集合与常用逻辑用语", None, 1),
        ("2.1.1", "集合的概念与运算", "2.1", 2),
        ("2.1.2", "充分条件与必要条件", "2.1", 2),
        ("2.2", "函数", None, 1),
        ("2.2.1", "函数的概念与性质", "2.2", 2),
        ("2.2.2", "基本初等函数", "2.2", 2),
        ("2.2.3", "函数与方程", "2.2", 2),
        ("2.3", "导数及其应用", None, 1),
        ("2.3.1", "导数的概念与运算", "2.3", 2),
        ("2.3.2", "导数在函数中的应用", "2.3", 2),
        ("2.3.3", "定积分", "2.3", 2),
        ("2.4", "三角函数", None, 1),
        ("2.4.1", "三角函数的概念与图像", "2.4", 2),
        ("2.4.2", "三角恒等变换", "2.4", 2),
        ("2.4.3", "解三角形", "2.4", 2),
        ("2.5", "数列", None, 1),
        ("2.5.1", "等差数列与等比数列", "2.5", 2),
        ("2.5.2", "数列求和", "2.5", 2),
        ("2.5.3", "数学归纳法", "2.5", 2),
        ("2.6", "不等式", None, 1),
        ("2.6.1", "基本不等式", "2.6", 2),
        ("2.6.2", "线性规划", "2.6", 2),
        ("2.7", "立体几何", None, 1),
        ("2.7.1", "空间几何体", "2.7", 2),
        ("2.7.2", "点线面位置关系", "2.7", 2),
        ("2.7.3", "空间向量与立体几何", "2.7", 2),
        ("2.8", "解析几何", None, 1),
        ("2.8.1", "直线与圆", "2.8", 2),
        ("2.8.2", "圆锥曲线", "2.8", 2),
        ("2.8.3", "参数方程与极坐标", "2.8", 2),
        ("2.9", "概率与统计", None, 1),
        ("2.9.1", "随机事件与概率", "2.9", 2),
        ("2.9.2", "统计与统计案例", "2.9", 2),
        ("2.9.3", "二项式定理", "2.9", 2),
        ("2.9.4", "随机变量及其分布", "2.9", 2),
        ("2.10", "向量", None, 1),
        ("2.10.1", "平面向量", "2.10", 2),
        ("2.10.2", "复数", "2.10", 2),
    ],
    "english": [
        ("3.1", "听力", None, 1),
        ("3.1.1", "短对话理解", "3.1", 2),
        ("3.1.2", "长对话理解", "3.1", 2),
        ("3.1.3", "短文理解", "3.1", 2),
        ("3.2", "阅读理解", None, 1),
        ("3.2.1", "细节理解题", "3.2", 2),
        ("3.2.2", "主旨大意题", "3.2", 2),
        ("3.2.3", "推理判断题", "3.2", 2),
        ("3.2.4", "词义猜测题", "3.2", 2),
        ("3.3", "完形填空", None, 1),
        ("3.4", "语法填空", None, 1),
        ("3.4.1", "时态语态", "3.4", 2),
        ("3.4.2", "非谓语动词", "3.4", 2),
        ("3.4.3", "定语从句", "3.4", 2),
        ("3.4.4", "名词性从句", "3.4", 2),
        ("3.4.5", "状语从句", "3.4", 2),
        ("3.4.6", "特殊句式", "3.4", 2),
        ("3.5", "写作", None, 1),
        ("3.5.1", "应用文写作", "3.5", 2),
        ("3.5.2", "读后续写", "3.5", 2),
        ("3.5.3", "概要写作", "3.5", 2),
    ],
    "physics": [
        ("4.1", "力学", None, 1),
        ("4.1.1", "运动学", "4.1", 2),
        ("4.1.2", "牛顿运动定律", "4.1", 2),
        ("4.1.3", "曲线运动", "4.1", 2),
        ("4.1.4", "万有引力与航天", "4.1", 2),
        ("4.1.5", "功与能", "4.1", 2),
        ("4.1.6", "动量", "4.1", 2),
        ("4.2", "电磁学", None, 1),
        ("4.2.1", "静电场", "4.2", 2),
        ("4.2.2", "恒定电流", "4.2", 2),
        ("4.2.3", "磁场", "4.2", 2),
        ("4.2.4", "电磁感应", "4.2", 2),
        ("4.2.5", "交变电流", "4.2", 2),
        ("4.3", "热学", None, 1),
        ("4.3.1", "分子动理论", "4.3", 2),
        ("4.3.2", "气体实验定律", "4.3", 2),
        ("4.3.3", "热力学定律", "4.3", 2),
        ("4.4", "光学", None, 1),
        ("4.5", "近代物理", None, 1),
        ("4.5.1", "原子结构", "4.5", 2),
        ("4.5.2", "原子核", "4.5", 2),
        ("4.5.3", "波粒二象性", "4.5", 2),
        ("4.6", "实验", None, 1),
    ],
    "chemistry": [
        ("5.1", "化学计量", None, 1),
        ("5.2", "物质结构与性质", None, 1),
        ("5.2.1", "原子结构", "5.2", 2),
        ("5.2.2", "分子结构", "5.2", 2),
        ("5.2.3", "晶体结构", "5.2", 2),
        ("5.3", "化学反应原理", None, 1),
        ("5.3.1", "化学反应与能量", "5.3", 2),
        ("5.3.2", "化学反应速率与化学平衡", "5.3", 2),
        ("5.3.3", "水溶液中的离子平衡", "5.3", 2),
        ("5.3.4", "电化学", "5.3", 2),
        ("5.4", "无机元素及其化合物", None, 1),
        ("5.4.1", "碱金属", "5.4", 2),
        ("5.4.2", "卤素", "5.4", 2),
        ("5.4.3", "氧族元素", "5.4", 2),
        ("5.4.4", "氮族元素", "5.4", 2),
        ("5.4.5", "碳族元素", "5.4", 2),
        ("5.4.6", "过渡元素", "5.4", 2),
        ("5.5", "有机化学", None, 1),
        ("5.5.1", "烃", "5.5", 2),
        ("5.5.2", "烃的衍生物", "5.5", 2),
        ("5.5.3", "生物大分子", "5.5", 2),
        ("5.5.4", "有机合成与推断", "5.5", 2),
        ("5.6", "化学实验", None, 1),
    ],
    "biology": [
        ("6.1", "细胞", None, 1),
        ("6.1.1", "细胞的分子组成", "6.1", 2),
        ("6.1.2", "细胞结构", "6.1", 2),
        ("6.1.3", "细胞的代谢", "6.1", 2),
        ("6.1.4", "细胞的生命历程", "6.1", 2),
        ("6.2", "遗传与进化", None, 1),
        ("6.2.1", "遗传的分子基础", "6.2", 2),
        ("6.2.2", "基因的传递规律", "6.2", 2),
        ("6.2.3", "生物的变异", "6.2", 2),
        ("6.2.4", "生物的进化", "6.2", 2),
        ("6.3", "稳态与环境", None, 1),
        ("6.3.1", "植物的激素调节", "6.3", 2),
        ("6.3.2", "神经与体液调节", "6.3", 2),
        ("6.3.3", "免疫调节", "6.3", 2),
        ("6.3.4", "种群与群落", "6.3", 2),
        ("6.3.5", "生态系统", "6.3", 2),
        ("6.4", "实验与探究", None, 1),
    ],
    "history": [
        ("7.1", "中国古代史", None, 1),
        ("7.1.1", "先秦时期", "7.1", 2),
        ("7.1.2", "秦汉时期", "7.1", 2),
        ("7.1.3", "魏晋南北朝", "7.1", 2),
        ("7.1.4", "隋唐时期", "7.1", 2),
        ("7.1.5", "宋元时期", "7.1", 2),
        ("7.1.6", "明清时期", "7.1", 2),
        ("7.2", "中国近代史", None, 1),
        ("7.2.1", "鸦片战争至甲午战争", "7.2", 2),
        ("7.2.2", "维新运动与辛亥革命", "7.2", 2),
        ("7.2.3", "新民主主义革命", "7.2", 2),
        ("7.2.4", "抗日战争与解放战争", "7.2", 2),
        ("7.3", "中国现代史", None, 1),
        ("7.3.1", "社会主义建设", "7.3", 2),
        ("7.3.2", "改革开放", "7.3", 2),
        ("7.4", "世界史", None, 1),
        ("7.4.1", "古代文明", "7.4", 2),
        ("7.4.2", "近代欧美", "7.4", 2),
        ("7.4.3", "两次世界大战", "7.4", 2),
        ("7.4.4", "二战后世界", "7.4", 2),
    ],
    "geography": [
        ("8.1", "自然地理", None, 1),
        ("8.1.1", "地球与地图", "8.1", 2),
        ("8.1.2", "大气运动与气候", "8.1", 2),
        ("8.1.3", "水循环与洋流", "8.1", 2),
        ("8.1.4", "地壳物质循环", "8.1", 2),
        ("8.1.5", "自然带", "8.1", 2),
        ("8.2", "人文地理", None, 1),
        ("8.2.1", "人口与城市化", "8.2", 2),
        ("8.2.2", "农业地域类型", "8.2", 2),
        ("8.2.3", "工业区位", "8.2", 2),
        ("8.2.4", "交通与通信", "8.2", 2),
        ("8.2.5", "可持续发展", "8.2", 2),
        ("8.3", "区域地理", None, 1),
        ("8.3.1", "中国地理", "8.3", 2),
        ("8.3.2", "世界地理", "8.3", 2),
    ],
    "politics": [
        ("9.1", "经济生活", None, 1),
        ("9.1.1", "货币与价格", "9.1", 2),
        ("9.1.2", "生产与消费", "9.1", 2),
        ("9.1.3", "收入与分配", "9.1", 2),
        ("9.1.4", "社会主义市场经济", "9.1", 2),
        ("9.1.5", "经济全球化", "9.1", 2),
        ("9.2", "政治生活", None, 1),
        ("9.2.1", "公民的政治生活", "9.2", 2),
        ("9.2.2", "政府", "9.2", 2),
        ("9.2.3", "人大与政党", "9.2", 2),
        ("9.2.4", "民族与宗教", "9.2", 2),
        ("9.2.5", "国际社会", "9.2", 2),
        ("9.3", "文化生活", None, 1),
        ("9.3.1", "文化传承与创新", "9.3", 2),
        ("9.3.2", "中华文化与民族精神", "9.3", 2),
        ("9.3.3", "中国特色社会主义文化", "9.3", 2),
        ("9.4", "哲学与生活", None, 1),
        ("9.4.1", "唯物论", "9.4", 2),
        ("9.4.2", "认识论", "9.4", 2),
        ("9.4.3", "辩证法", "9.4", 2),
        ("9.4.4", "唯物史观", "9.4", 2),
        ("9.4.5", "价值观与人生观", "9.4", 2),
    ],
}


async def seed_data() -> None:
    """初始化种子数据：科目、数据源、知识点"""
    async with aiosqlite.connect(DB_PATH) as db:
        for sid, info in {
            "chinese": ("语文", 150, 150),
            "math": ("数学", 150, 120),
            "english": ("英语", 150, 120),
            "physics": ("物理", 100, 75),
            "chemistry": ("化学", 100, 75),
            "biology": ("生物", 100, 75),
            "history": ("历史", 100, 75),
            "geography": ("地理", 100, 75),
            "politics": ("政治", 100, 75),
        }.items():
            await db.execute(
                "INSERT OR IGNORE INTO subjects (id, name, total_score, time_min) VALUES (?,?,?,?)",
                (sid, *info),
            )

        from config import SOURCES
        for sid, src_info in SOURCES.items():
            await db.execute(
                "INSERT OR IGNORE INTO sources (id, name, base_url, priority, enabled) VALUES (?,?,?,?,?)",
                (sid, src_info["name"], src_info["base_url"], src_info["priority"], 1 if src_info["enabled"] else 0),
            )

        for subject_id, kps in KNOWLEDGE_SEED.items():
            kp_map: dict[str | None, int] = {}
            for code, name, parent_code, level in kps:
                parent_id = kp_map.get(parent_code) if parent_code else None
                cursor = await db.execute(
                    "INSERT OR IGNORE INTO knowledge_points (subject_id, code, name, parent_id, level) VALUES (?,?,?,?,?)",
                    (subject_id, code, name, parent_id, level),
                )
                kp_id: Any = cursor.lastrowid
                kp_map[code] = kp_id

        await db.commit()


async def optimize_fts(db: Any = None) -> None:
    """优化 FTS5 索引：合并段、提升搜索精度（P-6）。

    Args:
        db: 可选的数据库连接；为 None 时内部创建新连接。
    """
    tables = ["papers_fts", "questions_fts"]
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            for table in tables:
                try:
                    await conn.execute(f"INSERT INTO {table}({table}) VALUES('optimize')")
                except Exception:  # noqa: BLE001
                    pass
            await conn.commit()
    else:
        for table in tables:
            try:
                await db.execute(f"INSERT INTO {table}({table}) VALUES('optimize')")
            except Exception:  # noqa: BLE001
                pass
        await db.commit()
