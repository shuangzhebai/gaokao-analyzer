# 高考模拟卷智能分析系统 · gaokao-analyzer

<p align="center">
  <img src="https://img.shields.io/github/stars/shuangzhebai/gaokao-analyzer?style=for-the-badge&logo=github" alt="stars"/>
  <img src="https://img.shields.io/github/actions/workflow/status/shuangzhebai/gaokao-analyzer/ci.yml?style=for-the-badge&logo=githubactions" alt="ci"/>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue?style=for-the-badge&logo=python" alt="python"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="license"/>
  <img src="https://img.shields.io/badge/coverage-92%25-brightgreen?style=for-the-badge" alt="coverage"/>
</p>

<p align="center">
  <b>🏆 IRT 心理测量 + 多Agent闭环 + 智能组卷 — 专为高考打造的 AI 学习系统</b>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-demo">Live Demo</a> •
  <a href="#-installation">Installation</a> •
  <a href="#%EF%B8%8F-configuration">Configuration</a> •
  <a href="#-api">API</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## ✨ Features

| Feature | Description | Status |
|---------|-------------|--------|
| **🎯 IRT 心理测量** | 3PL IRT 模型，精准评估学生能力 (θ) | ✅ Stable |
| **🧠 多Agent 闭环** | 诊断→规划→推荐→测评，全自动循环 | ✅ v7.1 |
| **🏆 游戏化激励** | 每日打卡、连续学习、成就徽章 | ✅ v7.2 |
| **🌐 知识图谱** | 知识点依赖DAG，力导向图可视化 | ✅ v7.2 |
| **🤖 AI 智能助教** | WebSocket 对话 + 降级模板回复 | ✅ v7.2 |
| **📚 课程管理** | 课程/章节/报名全流程 | ✅ v7.2 |
| **📝 作业批改系统** | 客观题自动批改 + 主观题待审 | ✅ v7.2 |
| **📊 数据看板** | 系统统计 + 学习趋势 + 个人进度 | ✅ v7.2 |
| **💬 社区论坛** | 问答/投票/热门话题 | ✅ v7.2 |
| **🏆 排行榜** | 日/周/月/全站 学习排行 | ✅ v7.2 |
| **🔔 通知系统** | 系统通知/学习提醒/已读管理 | ✅ v7.2 |
| **📄 学习报告** | HTML可打印报告 + 薄弱点分析 | ✅ v7.2 |
| **📱 PWA 移动端** | Manifest + Service Worker 就绪 | ✅ v7.2 |
| **🔄 多端同步** | 设备间数据同步API | ✅ v7.2 |
| **📝 错题本增强** | 间隔复习/CSV导出/同类推荐 | ✅ v7.2 |
| **📊 实时仪表盘** | ECharts能力轨迹/掌握度分布 | ✅ v7.2 |
| **📊 智能组卷** | OR-Tools CP-SAT，30秒生成最优试卷 | ✅ Stable |
| **🔍 FTS5 全文搜索** | 秒级检索 2万+ 试题 | ✅ Stable |
| **🤖 AI 个性化讲解** | DeepSeek 驱动，≤8秒生成结构化讲解 | ✅ v7.1 |
| **📈 掌握度追踪** | IRT 衰减曲线 + 间隔复习 (1/3/7/30天) | ✅ v7.1 |
| **📐 偏态分布模拟** | 正态/对数正态/指数分布，仿真真实考试成绩 | ✅ v6.0 |
| **🐳 一键部署** | Docker Compose，5分钟启动 | ✅ Stable |

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI App                        │
├──────────────┬──────────────┬──────────────────────┤
│  Agent Layer  │ Service Layer │    Data Layer        │
│               │              │                      │
│  Diagnosis ───┤ AgentAdapter ├─── SQLite/PostgreSQL  │
│  Planning  ───┤   (unified)  ├─── FTS5 Full-Text     │
│  Recommend ───┤              ├─── MeiliSearch        │
│  Assessment ──┤  ErrorReview ├─── Redis Cache        │
│               │  FC Tools    │                      │
├──────────────┴──────────────┴──────────────────────┤
│  Frontend: React + MUI + TypeScript (5 learning pages)│
│  Extras: Gamification / AI Chat / Dashboard          │
│  Deployment: Docker Compose / Uvicorn                 │
└──────────────────────────────────────────────────────┘
```

### Agent Orchestration

```
User → Diagnosis(IRT+CTT) → Planning(FC tools) → Recommendation(LLM) → Assessment(CAT)
         ↑                                                                    │
         └──────────────────── Feedback Loop ────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer

# 2. Install
pip install -r requirements.txt

# 3. Initialize database & seed data
python -c "import asyncio; from models import init_db, seed_data; asyncio.run(init_db()); asyncio.run(seed_data())"

# 4. Start
uvicorn app:app --host 0.0.0.0 --port 8000

# 5. Open browser → http://localhost:8000
```

### Docker (5 min)

```bash
docker compose up -d
```

### Seed textbook mappings

```bash
python scripts/seed_textbook_mappings.py
```

## 📦 Installation

### Prerequisites
- Python 3.13+
- Node.js 18+ (for frontend development)
- Docker (optional, for containerized deployment)

### From Source

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Database Setup

Supports two backends:

| Backend | Setup |
|---------|-------|
| **SQLite** (default) | Zero config — auto-created at `data/gaokao.db` |
| **PostgreSQL** | Set `DB_URL=postgresql://user:pass@host/db` in `.env` |

## ⚙️ Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `OPENAI_API_KEY` | — | DeepSeek/OpenAI API key for Agent LLM calls |
| `DB_PATH` | `data/gaokao.db` | SQLite database path |
| `DB_URL` | — | PostgreSQL connection string (overrides DB_PATH) |
| `REDIS_URL` | — | Redis connection string for caching |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `GAOKAO_ENV` | `development` | `development` / `production` |

## 📖 API

### Agent Orchestration (`/api/v1/agent/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/run` | Full agent cycle: diagnosis→planning→recommend→assess |
| POST | `/run/{agent}` | Run single agent by name |
| GET | `/session/{id}` | Get session status & results |
| GET | `/session/{id}/stream` | SSE stream of execution progress |
| GET | `/history` | User's agent session history |
| POST | `/explain` | F7: Structured knowledge explanation |

### Learning Center (`/api/v1/learning/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/paths` | Get learning paths |
| POST | `/paths` | Create learning path |
| GET | `/paths/{id}` | Get path details |
| PATCH | `/paths/{id}` | Update path progress |
| GET | `/progress` | Get learning progress |
| GET | `/reviews` | Get spaced review schedule |
| POST | `/reviews` | Start review session |
| GET | `/textbook/*` | Textbook mapping queries |

### Assessment (`/api/v1/assessment/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/list` | Get assessment history |
| GET | `/{id}` | Get assessment details |
| POST | `/{id}/submit` | Submit answers & get report |
| GET | `/report/{id}` | Get assessment report |

### Full API Documentation

```bash
# After starting the server:
open http://localhost:8000/docs  # Swagger UI
open http://localhost:8000/redoc  # ReDoc
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run specific test
pytest tests/test_v7_agents.py -v
```

## 🐳 Docker

```bash
# Build & start
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down

# Production deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Run pre-commit hooks (`pre-commit run --all-files`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing`)
6. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run linting
ruff check .
ruff format --check .
mypy agents/ services/ routes/
```

## 📊 Tech Stack

| Category | Technology |
|----------|-----------|
| **Backend** | Python 3.13+, FastAPI, Uvicorn |
| **AI/ML** | DeepSeek API, OR-Tools CP-SAT, SciPy |
| **Database** | SQLite + FTS5 / PostgreSQL, aiosqlite / asyncpg |
| **Search** | FTS5 full-text search, MeiliSearch |
| **Cache** | Redis |
| **Frontend** | React 18, TypeScript, MUI 5, React Router 6 |
| **DevOps** | Docker, Docker Compose, GitHub Actions |

## 📄 License

[MIT License](LICENSE) — feel free to use in commercial and personal projects.

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=shuangzhebai/gaokao-analyzer&type=Date)](https://star-history.com/#shuangzhebai/gaokao-analyzer&Date)

---

<p align="center">
  <b>If you find this project useful, please ⭐ star it on GitHub!</b>
  <br>
  <i>Built with ❤️ for every Chinese student preparing for gaokao</i>
</p>
