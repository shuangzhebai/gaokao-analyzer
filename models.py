"""
数据库模型 v6.0 - SQLite + aiosqlite + FTS5 + WAL模式极致优化
v6.0: WAL模式/synchronous=NORMAL/cache=8MB/mmap=256MB/foreign_keys=ON
"""
import aiosqlite
import logging
from typing import Any

from config import DB_PATH

logger = logging.getLogger("gaokao")


# ============ 版本化迁移（T01：防清空数据） ============

# 当前 schema 版本号。升级时请递增本常量并在 MIGRATIONS 中注册对应迁移函数。
CURRENT_SCHEMA_VERSION = 12


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


async def _migrate_to_v4(db: Any) -> None:
    """阶段四迁移 v4：新增用户与角色表。"""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS roles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            priority INTEGER DEFAULT 0
        )"""
    )
    await db.execute(
        """INSERT OR IGNORE INTO roles (id, name, description, priority) VALUES
            ('admin', '管理员', '系统管理员，拥有所有权限', 0),
            ('teacher', '教师', '可以上传、分析、查看试卷', 1),
            ('viewer', '查看者', '仅可查看和搜索', 2)"""
    )
    await db.execute(
        """CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        )"""
    )


async def _migrate_to_v5(db: Any) -> None:
    """阶段五迁移 v5：添加多租户 tenant_id 字段。"""
    # 给 papers 表加 tenant_id 列（幂等）
    try:
        await db.execute("ALTER TABLE papers ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass  # 列已存在则忽略
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_papers_tenant ON papers(tenant_id)")
    except Exception:
        pass
    # 给 users 表加 tenant_id 列
    try:
        await db.execute("ALTER TABLE users ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass


async def _migrate_to_v6(db: Any) -> None:
    """阶段六迁移 v6：添加 webhooks 表。"""
    await db.execute("""CREATE TABLE IF NOT EXISTS webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        events TEXT NOT NULL DEFAULT 'task.completed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_webhooks_user ON webhooks(user_id)")


async def _migrate_to_v7(db: Any) -> None:
    """阶段七迁移 v7：v6.0 新表 — 题型分类、错题库、学生画像、组卷模板与记录。"""
    # 1. question_types 表（题型分类）
    await db.execute("""CREATE TABLE IF NOT EXISTS question_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id TEXT NOT NULL,
        main_type TEXT NOT NULL,
        sub_type TEXT NOT NULL,
        name_cn TEXT NOT NULL,
        level INTEGER DEFAULT 1,
        parent_id INTEGER,
        FOREIGN KEY (parent_id) REFERENCES question_types(id)
    )""")
    # 2. questions 表新增列
    await _add_column_if_missing(db, "questions", "question_type_id", "INTEGER REFERENCES question_types(id)")
    await _add_column_if_missing(db, "questions", "irt_params_cache", "TEXT")
    # 3. error_records 表
    await db.execute("""CREATE TABLE IF NOT EXISTS error_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        subject_id TEXT NOT NULL,
        error_reason TEXT DEFAULT 'other',
        user_score REAL,
        question_score REAL DEFAULT 0,
        attempt_count INTEGER DEFAULT 1,
        is_mastered INTEGER DEFAULT 0,
        mastered_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        tenant_id TEXT,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )""")
    # 4. student_profiles 表
    await db.execute("""CREATE TABLE IF NOT EXISTS student_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject_id TEXT NOT NULL,
        theta REAL DEFAULT 0.0,
        theta_se REAL DEFAULT 1.0,
        knowledge_mastery TEXT DEFAULT '{}',
        total_questions INTEGER DEFAULT 0,
        correct_questions INTEGER DEFAULT 0,
        last_updated TEXT DEFAULT (datetime('now')),
        tenant_id TEXT,
        UNIQUE(user_id, subject_id)
    )""")
    # 5. paper_templates 表
    await db.execute("""CREATE TABLE IF NOT EXISTS paper_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        created_by TEXT NOT NULL,
        constraints_json TEXT NOT NULL DEFAULT '{}',
        description TEXT,
        is_public INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    # 6. composition_records 表
    await db.execute("""CREATE TABLE IF NOT EXISTS composition_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        template_id INTEGER,
        created_by TEXT NOT NULL,
        constraints_json TEXT NOT NULL DEFAULT '{}',
        question_ids_json TEXT NOT NULL DEFAULT '[]',
        quality_report_json TEXT,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (template_id) REFERENCES paper_templates(id)
    )""")


async def _migrate_to_v8(db: Any) -> None:
    """阶段八迁移 v8（P2-4）：JWT token 黑名单表。"""
    await db.execute("""CREATE TABLE IF NOT EXISTS token_blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jti TEXT NOT NULL UNIQUE,
        token_type TEXT DEFAULT 'access',
        user_id INTEGER NOT NULL,
        revoked_at TEXT DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL,
        tenant_id TEXT
    )""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(jti)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_token_blacklist_expires ON token_blacklist(expires_at)")


async def _migrate_to_v8_5(db: Any) -> None:
    """阶段八点五迁移 v8.5：采集日志表 collection_logs。"""
    await db.execute("""CREATE TABLE IF NOT EXISTS collection_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        task_type TEXT DEFAULT 'scheduled',
        started_at TEXT,
        completed_at TEXT,
        papers_found INTEGER DEFAULT 0,
        papers_new INTEGER DEFAULT 0,
        questions_new INTEGER DEFAULT 0,
        errors TEXT DEFAULT '[]',
        status TEXT DEFAULT 'running'
    )""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_collection_logs_status ON collection_logs(status)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_collection_logs_started ON collection_logs(started_at)")


async def _migrate_to_v10(db: Any) -> None:
    """v10: Agent 学习闭环 — 4张新表 + F7/F8 表结构变更"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS learning_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, subject_id TEXT NOT NULL,
            session_id TEXT NOT NULL, plan_json TEXT NOT NULL DEFAULT '{}',
            status TEXT DEFAULT 'active', progress_pct REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            tenant_id TEXT DEFAULT 'default',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_lp_user_subject ON learning_paths(user_id, subject_id);
        CREATE INDEX IF NOT EXISTS idx_lp_session ON learning_paths(session_id);
        CREATE INDEX IF NOT EXISTS idx_lp_status ON learning_paths(status);
        CREATE TABLE IF NOT EXISTS stage_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            subject_id TEXT NOT NULL, learning_path_id INTEGER,
            session_id TEXT NOT NULL, composition_id INTEGER,
            score REAL, total_score REAL, theta_before REAL, theta_after REAL, theta_shift REAL,
            weakness_before JSON DEFAULT '[]', weakness_after JSON DEFAULT '[]',
            weakness_resolved JSON DEFAULT '[]', diagnosis_json TEXT,
            recommendations JSON DEFAULT '[]', status TEXT DEFAULT 'pending',
            started_at TEXT, completed_at TEXT, created_at TEXT DEFAULT (datetime('now')),
            tenant_id TEXT DEFAULT 'default',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (learning_path_id) REFERENCES learning_paths(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sa_user_subject ON stage_assessments(user_id, subject_id);
        CREATE INDEX IF NOT EXISTS idx_sa_session ON stage_assessments(session_id);
        CREATE TABLE IF NOT EXISTS textbook_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id TEXT NOT NULL,
            textbook_name TEXT NOT NULL, chapter_code TEXT NOT NULL,
            chapter_name TEXT NOT NULL, section_code TEXT, section_name TEXT,
            kp_code TEXT NOT NULL, kp_name TEXT NOT NULL,
            weight REAL DEFAULT 1.0, page_range TEXT, mapping_type TEXT DEFAULT 'chapter',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tm_unique ON textbook_mappings(subject_id, textbook_name, chapter_code, section_code, kp_code);
        CREATE TABLE IF NOT EXISTS agent_execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            agent_name TEXT NOT NULL, user_id INTEGER NOT NULL,
            subject_id TEXT NOT NULL, state_from TEXT, state_to TEXT,
            model TEXT DEFAULT 'deepseek-chat', prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER, tool_calls_json TEXT DEFAULT '[]',
            success INTEGER DEFAULT 1, error_msg TEXT, output_summary TEXT,
            created_at TEXT DEFAULT (datetime('now')), tenant_id TEXT DEFAULT 'default',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_ael_session ON agent_execution_logs(session_id);
        CREATE INDEX IF NOT EXISTS idx_ael_user_agent ON agent_execution_logs(user_id, agent_name);
        CREATE INDEX IF NOT EXISTS idx_ael_success ON agent_execution_logs(success);
    """)


async def _migrate_to_v10_5(db: Any) -> None:
    """v10.5: F8 error_records复习字段 + F7 knowledge_explanations表"""
    # F8: error_records 增加间隔复习字段（ALTER TABLE 逐个执行）
    try:
        await db.execute("ALTER TABLE error_records ADD COLUMN review_schedule TEXT")
    except Exception:
        pass  # 字段已存在
    try:
        await db.execute("ALTER TABLE error_records ADD COLUMN next_review_at TEXT")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE error_records ADD COLUMN review_interval_days INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE error_records ADD COLUMN review_count INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE error_records ADD COLUMN mastery_at_last_review REAL")
    except Exception:
        pass
    # F7: 知识点讲解模板表
    await db.execute("""CREATE TABLE IF NOT EXISTS knowledge_explanations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kp_code TEXT NOT NULL,
        subject_id TEXT NOT NULL, version TEXT DEFAULT 'v1',
        concept_summary TEXT NOT NULL, key_difficulty TEXT,
        example_question_ids TEXT DEFAULT '[]', common_mistakes TEXT,
        prerequisite_kps TEXT DEFAULT '[]', created_at TEXT DEFAULT (datetime('now'))
    )""")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ke_kp ON knowledge_explanations(kp_code, subject_id)")



async def _migrate_to_v11(db: Any) -> None:
    """v12: 游戏化激励 + 知识图谱持久化"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS user_streaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            subject_id TEXT NOT NULL, current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0, last_study_date TEXT,
            total_study_days INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime("now")),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_us_user_subject ON user_streaks(user_id, subject_id);
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            achievement_code TEXT NOT NULL, achievement_name TEXT NOT NULL,
            description TEXT, icon_url TEXT, unlocked_at TEXT DEFAULT (datetime("now")),
            is_new INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ua_user_ach ON user_achievements(user_id, achievement_code);
        CREATE TABLE IF NOT EXISTS knowledge_graph (
            kp_code TEXT PRIMARY KEY, kp_name TEXT NOT NULL,
            subject_id TEXT NOT NULL, prerequisites TEXT DEFAULT "[]",
            difficulty REAL DEFAULT 0.5, exam_frequency REAL DEFAULT 0.0,
            cognitive_level TEXT DEFAULT "u57fau7840", importance TEXT DEFAULT "u4e2d",
            children TEXT DEFAULT "[]", related_kps TEXT DEFAULT "[]"
        );
        CREATE INDEX IF NOT EXISTS idx_kg_subject ON knowledge_graph(subject_id);
    
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT DEFAULT '', subject_id TEXT NOT NULL,
            difficulty TEXT DEFAULT 'medium', estimated_hours REAL DEFAULT 0,
            cover_url TEXT, status TEXT DEFAULT 'draft',
            created_by INTEGER, created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS course_chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL,
            title TEXT NOT NULL, content_type TEXT DEFAULT 'video',
            content_url TEXT, duration_minutes INTEGER DEFAULT 0,
            order_index INTEGER DEFAULT 0, kp_codes TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS course_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL, progress_pct REAL DEFAULT 0,
            enrolled_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT, FOREIGN KEY (course_id) REFERENCES courses(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ce_user_course ON course_enrollments(user_id, course_id);
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT DEFAULT '', course_id INTEGER,
            subject_id TEXT NOT NULL, questions TEXT DEFAULT '[]',
            due_at TEXT, created_by INTEGER, status TEXT DEFAULT 'published',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, answers TEXT DEFAULT '[]',
            score REAL DEFAULT 0, total_score REAL DEFAULT 0,
            status TEXT DEFAULT 'pending', submitted_at TEXT DEFAULT (datetime('now')),
            graded_at TEXT, grader_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS sync_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL, data_json TEXT DEFAULT '{}',
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_sr_user_device ON sync_records(user_id, device_id);
    """)
    await db.commit()

async def _migrate_to_v12(db: Any) -> None:
    """v12: 社区论坛 + 通知 + 多端同步"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS forum_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            content TEXT NOT NULL, subject_id TEXT NOT NULL,
            tags TEXT DEFAULT '[]', kp_code TEXT, user_id INTEGER NOT NULL,
            author_name TEXT, answer_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0, is_resolved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_fq_subject ON forum_questions(subject_id);
        CREATE TABLE IF NOT EXISTS forum_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL,
            content TEXT NOT NULL, user_id INTEGER NOT NULL,
            author_name TEXT, votes INTEGER DEFAULT 0,
            is_accepted INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (question_id) REFERENCES forum_questions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_fa_question ON forum_answers(question_id);
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            title TEXT NOT NULL, content TEXT NOT NULL,
            notification_type TEXT DEFAULT 'system',
            link TEXT DEFAULT '', is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read);
    """)
