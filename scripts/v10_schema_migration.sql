"""v10: Agent学习闭环 Schema迁移
-- 4张新表 + 2表修改
-- 对应 Spec v1.2，需集成到 models.py MIGRATIONS
"""

V10_SQL = """
-- ============================================================
-- v10.0: Agent 学习闭环 — 4张新表
-- ============================================================

-- 1. learning_paths — 学习路径表（规划Agent输出）
CREATE TABLE IF NOT EXISTS learning_paths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    subject_id      TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    plan_json       TEXT NOT NULL DEFAULT '{}',
    status          TEXT DEFAULT 'active',
    progress_pct    REAL DEFAULT 0.0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    tenant_id       TEXT DEFAULT 'default',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lp_user_subject ON learning_paths(user_id, subject_id);
CREATE INDEX IF NOT EXISTS idx_lp_session ON learning_paths(session_id);
CREATE INDEX IF NOT EXISTS idx_lp_status ON learning_paths(status);

-- 2. stage_assessments — 阶段测评表（测评Agent输出）
CREATE TABLE IF NOT EXISTS stage_assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    subject_id      TEXT NOT NULL,
    learning_path_id INTEGER,
    session_id      TEXT NOT NULL,
    composition_id  INTEGER,
    score           REAL,
    total_score     REAL,
    theta_before    REAL,
    theta_after     REAL,
    theta_shift     REAL,
    weakness_before JSON DEFAULT '[]',
    weakness_after  JSON DEFAULT '[]',
    weakness_resolved JSON DEFAULT '[]',
    diagnosis_json  TEXT,
    recommendations JSON DEFAULT '[]',
    status          TEXT DEFAULT 'pending',
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    tenant_id       TEXT DEFAULT 'default',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (learning_path_id) REFERENCES learning_paths(id),
    FOREIGN KEY (composition_id) REFERENCES composition_records(id)
);

CREATE INDEX IF NOT EXISTS idx_sa_user_subject ON stage_assessments(user_id, subject_id);
CREATE INDEX IF NOT EXISTS idx_sa_session ON stage_assessments(session_id);
CREATE INDEX IF NOT EXISTS idx_sa_path ON stage_assessments(learning_path_id);
CREATE INDEX IF NOT EXISTS idx_sa_created ON stage_assessments(created_at);

-- 3. textbook_mappings — 教材章节映射表
CREATE TABLE IF NOT EXISTS textbook_mappings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id      TEXT NOT NULL,
    textbook_name   TEXT NOT NULL,
    chapter_code    TEXT NOT NULL,
    chapter_name    TEXT NOT NULL,
    section_code    TEXT,
    section_name    TEXT,
    kp_code         TEXT NOT NULL,
    kp_name         TEXT NOT NULL,
    weight          REAL DEFAULT 1.0,
    page_range      TEXT,
    mapping_type    TEXT DEFAULT 'chapter',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (kp_code) REFERENCES knowledge_points(code)
);

CREATE INDEX IF NOT EXISTS idx_tm_subject_kp ON textbook_mappings(subject_id, kp_code);
CREATE INDEX IF NOT EXISTS idx_tm_textbook ON textbook_mappings(subject_id, textbook_name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tm_unique ON textbook_mappings(subject_id, textbook_name, chapter_code, section_code, kp_code);

-- 4. agent_execution_logs — Agent执行日志表
CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    user_id         INTEGER NOT NULL,
    subject_id      TEXT NOT NULL,
    state_from      TEXT,
    state_to        TEXT,
    model           TEXT DEFAULT 'deepseek-chat',
    prompt_tokens   INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    latency_ms      INTEGER,
    tool_calls_json TEXT DEFAULT '[]',
    success         INTEGER DEFAULT 1,
    error_msg       TEXT,
    output_summary  TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    tenant_id       TEXT DEFAULT 'default',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ael_session ON agent_execution_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_ael_user_agent ON agent_execution_logs(user_id, agent_name);
CREATE INDEX IF NOT EXISTS idx_ael_created ON agent_execution_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_ael_success ON agent_execution_logs(success);
"""

V10_5_SQL = """
-- ============================================================
-- v10.5: F7+F8 — 表结构变更
-- ============================================================

-- F8: error_records 增加间隔复习字段
ALTER TABLE error_records ADD COLUMN review_schedule TEXT;
ALTER TABLE error_records ADD COLUMN next_review_at TEXT;
ALTER TABLE error_records ADD COLUMN review_interval_days INTEGER DEFAULT 1;
ALTER TABLE error_records ADD COLUMN review_count INTEGER DEFAULT 0;
ALTER TABLE error_records ADD COLUMN mastery_at_last_review REAL;

-- F7: 知识点讲解模板表
CREATE TABLE IF NOT EXISTS knowledge_explanations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kp_code         TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    version         TEXT DEFAULT 'v1',
    concept_summary TEXT NOT NULL,
    key_difficulty  TEXT,
    example_question_ids TEXT DEFAULT '[]',
    common_mistakes TEXT,
    prerequisite_kps  TEXT DEFAULT '[]',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (kp_code) REFERENCES knowledge_points(code)
);

CREATE INDEX IF NOT EXISTS idx_ke_kp ON knowledge_explanations(kp_code, subject_id);
"""
