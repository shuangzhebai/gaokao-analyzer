# 高考模拟卷智能分析系统 v4.0 — 架构设计文档

## 一、系统架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (index.html)                      │
│  Apple Design UI + Tailwind CSS + Chart.js               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│  │仪表盘│ │试卷库│ │详情页│ │采集站│ │分析页│          │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘          │
└─────┼────────┼────────┼────────┼────────┼───────────────┘
      │ REST API (JSON)
┌─────┴────────┴────────┴────────┴────────┴───────────────┐
│                   FastAPI 后端                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│  │papers│ │search│ │dedup │ │analyz│ │scraper│          │
│  │.py   │ │.py   │ │.py   │ │.py   │ │.py    │          │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘          │
│     └────────┴────────┴────────┴────────┘               │
│                    SQLite + FTS5                          │
└──────────────────────────────────────────────────────────┘
                    ↕ HTTP (按需)
              DeepSeek API (查重)
```

## 二、数据库设计

### 2.1 核心表结构

```sql
-- 科目表（不变）
CREATE TABLE subjects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    total_score INTEGER NOT NULL DEFAULT 150,
    time_min INTEGER NOT NULL DEFAULT 120
);

-- 数据源表（增强）
CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT,
    priority TEXT NOT NULL DEFAULT 'B',  -- S/A/B/C 可信度等级
    enabled INTEGER NOT NULL DEFAULT 1,
    rate_limit INTEGER DEFAULT 3,         -- 每分钟请求限制
    description TEXT
);

-- 试卷表（重设计）
CREATE TABLE papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    paper_type TEXT NOT NULL,              -- real/provincial/school/monthly/special
    year INTEGER NOT NULL,
    province TEXT,
    school TEXT,
    exam_tag TEXT,                          -- 一模/二模/省质检 等

    -- 来源追溯（P0）
    source_id TEXT,                         -- 数据源
    source_url TEXT,                        -- 原始链接
    source_priority TEXT DEFAULT 'B',       -- 来源可信度 S/A/B/C
    collected_at TIMESTAMP,                 -- 采集时间
    collector TEXT DEFAULT 'system',        -- 采集方式：system/manual/api
    verified INTEGER DEFAULT 0,             -- 是否已验证
    verified_at TIMESTAMP,                  -- 验证时间

    -- 内容
    file_path TEXT,
    total_score REAL DEFAULT 150,
    difficulty REAL,
    question_count INTEGER DEFAULT 0,

    -- 分析结果
    quality_score REAL,
    curriculum_score REAL,
    analysis_status TEXT DEFAULT 'pending', -- pending/parsed/irt_estimated/simulated
    curriculum_json TEXT,
    quality_json TEXT,
    simulation_json TEXT,

    -- 去重标记
    content_hash TEXT,                      -- 内容哈希，用于快速去重
    duplicate_of INTEGER,                   -- 重复试卷ID
    dedup_status TEXT DEFAULT 'unique',     -- unique/suspected/duplicate

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (duplicate_of) REFERENCES papers(id)
);

-- 题目表（增强）
CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    q_number INTEGER NOT NULL,
    q_type TEXT NOT NULL,                   -- choice/fill/solve
    content TEXT,
    options TEXT,                           -- JSON
    answer TEXT,
    explanation TEXT,                        -- 解析（新增）
    score REAL NOT NULL DEFAULT 0,
    knowledge_points TEXT,                  -- JSON 数组
    difficulty_tag TEXT,                     -- easy/medium/hard（新增）

    -- IRT 参数
    irt_a REAL,
    irt_b REAL,
    irt_c REAL DEFAULT 0.0,
    discrimination REAL,

    -- 课标与质量
    cognitive_level TEXT,
    core_competency TEXT,
    quality_rating TEXT,                    -- excellent/good/average/poor
    is_quality INTEGER DEFAULT 0,

    -- 去重
    content_hash TEXT,                      -- 题目内容哈希
    similar_to INTEGER,                     -- 相似题目ID

    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- 知识点表（不变）
CREATE TABLE knowledge_points (
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

-- 分析结果表（不变）
CREATE TABLE analysis_results (
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

-- 爬取日志表（增强）
CREATE TABLE scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    url TEXT,
    status TEXT NOT NULL,                   -- success/duplicate/error/skipped
    error_msg TEXT,
    paper_id INTEGER,
    dedup_result TEXT,                      -- unique/suspected/duplicate
    response_time_ms INTEGER,               -- 响应时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 去重记录表（新增）
CREATE TABLE dedup_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id_1 INTEGER NOT NULL,
    paper_id_2 INTEGER NOT NULL,
    similarity REAL NOT NULL,               -- 0-1 相似度
    method TEXT NOT NULL,                   -- hash/deepseek/manual
    status TEXT DEFAULT 'pending',          -- pending/confirmed/rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id_1) REFERENCES papers(id),
    FOREIGN KEY (paper_id_2) REFERENCES papers(id)
);
```

### 2.2 FTS5 全文搜索索引

```sql
-- 试卷全文搜索
CREATE VIRTUAL TABLE papers_fts USING fts5(
    title,
    province,
    school,
    exam_tag,
    subject_name,
    content='papers',
    content_rowid='id',
    tokenize='unicode61'  -- 支持中文（Unicode分词）
);

-- 题目全文搜索
CREATE VIRTUAL TABLE questions_fts USING fts5(
    content,
    knowledge_points,
    content='questions',
    content_rowid='id',
    tokenize='unicode61'
);
```

### 2.3 索引

```sql
CREATE INDEX idx_papers_subject ON papers(subject_id);
CREATE INDEX idx_papers_type ON papers(paper_type);
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_province ON papers(province);
CREATE INDEX idx_papers_source_priority ON papers(source_priority);
CREATE INDEX idx_papers_content_hash ON papers(content_hash);
CREATE INDEX idx_papers_dedup ON papers(dedup_status);
CREATE INDEX idx_papers_exam_tag ON papers(exam_tag);
CREATE INDEX idx_papers_composite ON papers(subject_id, year, paper_type);
CREATE INDEX idx_questions_paper ON questions(paper_id);
CREATE INDEX idx_questions_quality ON questions(is_quality);
CREATE INDEX idx_questions_hash ON questions(content_hash);
CREATE INDEX idx_kp_subject ON knowledge_points(subject_id);
CREATE INDEX idx_analysis_paper ON analysis_results(paper_id);
CREATE INDEX idx_scrape_status ON scrape_logs(status, created_at);
CREATE INDEX idx_dedup_papers ON dedup_records(paper_id_1, paper_id_2);
```

## 三、API 设计

### 3.1 搜索 API（P0 重写）

```
GET /api/search?q=深圳二模&subject=math&year=2026&type=school&province=广东&page=1&size=20&sort=relevance
```

响应：
```json
{
  "total": 42,
  "page": 1,
  "size": 20,
  "query": "深圳二模",
  "data": [
    {
      "id": 1,
      "title": "2026年广东省深圳市高三第二次模拟考试数学试卷",
      "subject_id": "math",
      "paper_type": "school",
      "year": 2026,
      "province": "深圳",
      "exam_tag": "二模",
      "source_priority": "B",
      "verified": true,
      "question_count": 22,
      "analysis_status": "simulated",
      "snippets": ["<em>深圳</em>高三第二次<em>二模</em>..."]
    }
  ]
}
```

### 3.2 查重 API（新增）

```
POST /api/papers/dedup
Body: { "title": "...", "questions": [...] }
Response: {
  "status": "unique|suspected|duplicate",
  "similar_papers": [
    { "paper_id": 5, "title": "...", "similarity": 0.85 }
  ]
}
```

### 3.3 其他 API（保留+增强）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/dashboard | 仪表盘统计 |
| GET | /api/search | 全文搜索（重写） |
| GET | /api/papers | 试卷列表（保留） |
| GET | /api/papers/{id} | 试卷详情（增强） |
| DELETE | /api/papers/{id} | 删除试卷 |
| POST | /api/papers/upload | 上传试卷（增加查重） |
| POST | /api/papers/dedup | 查重检测（新增） |
| POST | /api/papers/{id}/estimate-irt | IRT 参数估计 |
| POST | /api/papers/{id}/simulate | 成绩模拟 |
| POST | /api/papers/{id}/curriculum-analysis | 课标分析 |
| POST | /api/papers/{id}/quality-analysis | 质量评估 |
| POST | /api/analysis/fit | 拟合分析 |
| GET | /api/filters | 筛选选项元数据 |
| GET | /api/scrape/status | 采集状态 |
| POST | /api/scrape/collect | 触发采集 |
| GET | /api/quality-questions | 优质题推荐 |
| GET | /api/search/suggest | 搜索建议（新增） |

## 四、文件结构

```
gaokao-analyzer/
├── app.py              # FastAPI 主应用（重写路由和异常处理）
├── config.py           # 配置文件（增强 DeepSeek 配置）
├── models.py           # 数据库模型（重写 schema + FTS5）
├── search.py           # 搜索引擎（新增，FTS5 + 排名算法）
├── dedup.py            # 查重引擎（新增，hash + DeepSeek API）
├── scraper.py          # 爬虫引擎（增强，来源验证 + 去重）
├── parser.py           # 试卷解析器（保留）
├── analyzer.py         # IRT + 知识点分析（保留）
├── simulator.py        # 蒙特卡洛模拟（保留）
├── curriculum.py       # 课标分析（保留）
├── quality.py          # 质量评估（保留）
├── start.py            # 启动脚本（保留）
├── static/
│   └── index.html      # 前端页面（完全重写，Apple Design）
├── data/
│   └── gaokao.db       # SQLite 数据库
└── docs/
    ├── PRD-v4.md       # 产品需求文档
    └── ARCH-v4.md      # 架构设计文档
```

## 五、DeepSeek 集成方案

### 5.1 查重流程

```
新试卷 → 1. content_hash 快速比对（O(1)）
        → 2. FTS5 标题相似搜索（O(log n)）
        → 3. DeepSeek API 语义相似度（按需，有频率限制）
        → 判定：unique / suspected / duplicate
```

### 5.2 API 调用设计

```python
# dedup.py
class DedupEngine:
    def __init__(self, deepseek_api_key=None):
        self.api_key = deepseek_api_key
        self.api_url = "https://api.deepseek.com/v1/chat/completions"

    async def check_duplicate(self, paper_data: dict) -> dict:
        # Level 1: hash 比对
        hash_result = await self._hash_check(paper_data)
        if hash_result["status"] == "duplicate":
            return hash_result

        # Level 2: FTS5 标题搜索
        fts_result = await self._fts_check(paper_data)
        if not fts_result["similar_papers"]:
            return {"status": "unique", "similar_papers": []}

        # Level 3: DeepSeek 语义分析
        if self.api_key:
            return await self._deepseek_check(paper_data, fts_result)

        return fts_result

    async def _deepseek_check(self, paper_data, candidates):
        """调用 DeepSeek 判断语义相似度"""
        # 只对候选集调用，控制 API 调用量
        ...
```

### 5.3 频率控制
- hash 比对：无限制
- FTS5 搜索：无限制
- DeepSeek API：每分钟最多 10 次调用，超出排队

## 六、前端架构

### 6.1 页面结构

```
┌─────────────────────────────────────────────────────────────┐
│  ☁ 高考分析中心         [🔍 搜索试卷...]         [采集] [≡] │ ← 毛玻璃导航栏
├──────┬──────────────────────────────────────────────────────┤
│      │                                                      │
│ 全部 │   📊 统计卡片 (4列)                                  │
│ 语文 │   ┌───┐ ┌───┐ ┌───┐ ┌───┐                           │
│ 数学 │   │试卷│ │已分析│ │真题│ │优质题│                      │
│ 英语 │   └───┘ └───┘ └───┘ └───┘                           │
│ 物理 │                                                      │
│ 化学 │   📋 最近试卷                                       │
│ 生物 │   ┌──────────────────────────────────────┐           │
│ 历史 │   │ 2026深圳二模数学  深圳·二模  ★已验证  │           │
│ 地理 │   │ 2025全国甲卷数学  全国·真题  ★已验证  │           │
│ 政治 │   └──────────────────────────────────────┘           │
│      │                                                      │
└──────┴──────────────────────────────────────────────────────┘
```

### 6.2 CSS 设计规范

```css
:root {
    /* Apple Design 配色 */
    --apple-blue: #007AFF;
    --apple-green: #34C759;
    --apple-orange: #FF9500;
    --apple-red: #FF3B30;
    --apple-purple: #AF52DE;
    --apple-gray-1: #8E8E93;
    --apple-gray-2: #AEAEB2;
    --apple-gray-3: #C7C7CC;
    --apple-gray-4: #D1D1D6;
    --apple-gray-5: #E5E5EA;
    --apple-gray-6: #F2F2F7;

    --bg: #FFFFFF;
    --bg-secondary: #F5F5F7;
    --text-primary: #1D1D1F;
    --text-secondary: #86868B;

    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;

    --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
    --shadow-lg: 0 8px 30px rgba(0,0,0,0.12);

    --font: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text',
            'PingFang SC', 'Microsoft YaHei', sans-serif;
}
```

## 七、任务列表（按实现顺序）

### Phase 1: 数据库重设计 + 搜索引擎 (核心基础)

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| T1 | 重写 models.py schema + FTS5 | models.py | - |
| T2 | 新建 search.py 搜索引擎 | search.py | T1 |
| T3 | 重写 app.py 搜索路由 | app.py | T2 |

### Phase 2: 查重引擎 + 来源验证 (数据质量)

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| T4 | 新建 dedup.py 查重引擎 | dedup.py | T1 |
| T5 | 增强 scraper.py 来源验证 | scraper.py | T4 |
| T6 | app.py 查重路由 + 采集增强 | app.py | T4,T5 |

### Phase 3: 前端 Apple Design 重写 (UI)

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| T7 | 重写 index.html (Apple Design + 搜索 + 筛选) | index.html | T3 |
| T8 | 试卷详情页 | index.html | T7 |
| T9 | 仪表盘 + 采集页 | index.html | T7 |

### Phase 4: 稳定性 + 测试

| # | 任务 | 文件 | 依赖 |
|---|------|------|------|
| T10 | 全局异常处理 + 事务安全 | app.py | T6 |
| T11 | 输入验证 + 请求限流 | app.py | T10 |
| T12 | 集成测试 | test_*.py | T11 |

## 八、依赖包列表

```
# 保留
fastapi>=0.104.0
uvicorn>=0.24.0
aiosqlite>=0.19.0
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
numpy>=1.26.0
scipy>=1.11.0

# 新增（无，保持轻量）
# DeepSeek 查重使用 httpx 调用 API，无需额外包
```

## 九、共享知识（跨文件约定）

1. **数据库连接**：所有 DB 操作通过 `get_db()` 获取连接，使用 `async for` 确保释放
2. **FTS 同步**：papers 写入后必须同步到 papers_fts（通过 triggers 或手动 INSERT）
3. **错误处理**：所有 API 统一返回 `{"detail": "中文错误信息"}` 格式
4. **分页参数**：统一使用 `page` + `size`，默认 size=20
5. **内容哈希**：使用 SHA-256，对 title + subject + year + 前N道题 content 取哈希
6. **来源优先级映射**：S=教育部, A=省级, B=学科网/菁优网, C=个人上传
7. **Apple Blue**：主色调统一使用 #007AFF
