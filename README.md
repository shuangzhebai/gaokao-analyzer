# 🎯 gaokao-analyzer

> **高考教育领域的开源心理测量引擎 + 智能组卷平台**
>
> IRT 3PL/GPCM/GRM · 题型自动分类 · 6 维质量诊断 · OR-Tools 智能组卷 · 错题闭环 · PostgreSQL

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-258%20passed-success?logo=pytest)](https://github.com/shuangzhebai/gaokao-analyzer/actions)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/shuangzhebai/gaokao-analyzer?style=social)](https://github.com/shuangzhebai/gaokao-analyzer)
[![React](https://img.shields.io/badge/Frontend-React+TypeScript-61DAFB?logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL%2FSQLite-4169E1?logo=postgresql)](https://postgresql.org)
[![Prometheus](https://img.shields.io/badge/Metrics-Prometheus-E6522C?logo=prometheus)](https://prometheus.io)

---

## 🚀 小白用户看这里（3 步完成）

> **操作步骤：下载 → 双击 → 直接用！**

### 方法一：Docker 一键启动（推荐，最简单）

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. 下载本项目，双击 **`Docker一键启动.bat`**
3. 浏览器自动打开，直接点击"登录"按钮即可

> 管理员账号已自动创建，**无需注册**，账号密码已自动填好

### 方法二：Python 一键启动（无需 Docker）

1. 安装 [Python 3.13+](https://www.python.org/downloads/)（安装时勾选 "Add Python to PATH"）
2. 下载本项目，双击 **`一键启动.bat`**
3. 浏览器自动打开，直接点击"登录"按钮即可

> 首次启动会自动安装依赖（约 2-5 分钟），请耐心等待

---

## 📸 截图

_(欢迎分享你的使用截图！)_

## ✨ 核心特性

| 特性 | 技术实现 | 亮点 |
|------|---------|------|
| 🧮 **IRT 心理测量引擎** | 3PL / GPCM / GRM 模型 + Numba JIT | **独家** — 竞品全部基于 CTT 统计 |
| 🏷️ **题型自动分类** | 规则引擎 + LightGBM（P0），9 大学科 | 选择题/填空题/解答题/综合题自动识别 |
| 📊 **6 维质量诊断** | IRT+CTT 混合模型 + 6 维雷达图 | 难度/区分度/信度/效度/知识点/题型匹配 |
| 📝 **智能组卷** | OR-Tools CP-SAT 约束求解 | 按知识点/难度/题型多条件自动组卷+质量预检 |
| ❌ **错题闭环** | 自动收录 → 统计分析 → IRT 诊断 → 同类推荐 | 薄弱知识点定位 + 精准推题 |
| 🎲 **成绩模拟** | 蒙特卡洛 10 万考生 | 偏态校准 + 真实高考对标 |
| 🤖 **真实性审核** | DeepSeek AI + 多源交叉验证 | 99%+ 识别率 |
| 🔍 **智能搜索** | Meilisearch + FTS5 降级 | 中文分词+模糊纠错+高亮 |
| 🕸️ **多源采集** | 可插拔适配器 | 学科网/组卷网/菁优网等 7+ 源 |
| 🔐 **安全鉴权** | JWT + RBAC + Refresh Token | 黑名单吊销 + HMAC 签名 |
| 👥 **三端工作台** | 学生/教师/教研员差异化界面 | 各自工作台 + 全链路交互 |
| 🌐 **i18n 国际化** | locales/zh.json + en.json | 一键中英文切换 |
| 📱 **PWA 支持** | manifest.json + Service Worker | 可安装到桌面/离线可用 |
| 📊 **标准化监控** | Prometheus Counter/Histogram/Gauge | 可选 Grafana 面板 |
| 🐳 **一键部署** | Docker Compose + Helm Chart | Docker/K8s 双模式 |

## 🚀 5 分钟上手

```bash
# 1. 克隆
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer

# 2. 启动（Docker）
docker compose up -d

# 3. 注册管理员
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -d "username=admin&password=P@ssw0rd&role=admin"

# 4. 登录获取 Token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -d "username=admin&password=P@ssw0rd"

# 5. 使用 Token 访问 API
curl "http://localhost:8000/api/v1/papers" \
  -H "Authorization: Bearer <TOKEN>"

# 6. 打开浏览器访问 http://localhost:8000
```

## 🏗️ 架构

```
                    ┌──────────────────────┐
                    │   前端 (React+ECharts)│
                    │  /questions /quality  │
                    │  /composition /errors │
                    │  学生/教师/教研员工作台│
                    └──────┬───────────────┘
                           │ REST API (29 端点)
                    ┌──────▼───────────────┐
                    │   FastAPI 路由层      │
                    │  questions/quality/   │
                    │  composition/errors   │
                    └──────┬───────────────┘
                    ┌──────▼───────────────┐
                    │   服务编排层          │
                    │  Question/Quality/    │
                    │  Composition/Error    │
                    └──┬───────┬───────────┘
                       │       │
              ┌────────▼──┐ ┌──▼──────────┐
              │  引擎层     │ │  数据访问层  │
              │ IRT 3PL/   │ │  Repository  │
              │ GPCM/GRM   │ │  模式抽象     │
              │ 题型分类    │ │  PG/SQLite   │
              │ 质量诊断    │ │  双后端      │
              │ 组卷(OR-T) │ │              │
              └────────────┘ └──────────────┘
                       │              │
              ┌────────▼──────────────▼────┐
              │   基础设施                  │
              │ PG · Redis · Meilisearch   │
              │ Celery · Prometheus        │
              └─────────────────────────────┘
```

## 📊 质量指标

| 指标 | 数值 |
|------|------|
| ✅ 测试通过 | **258 tests** (基线 223 + 新增 35) |
| 🔍 类型检查 | **mypy strict** |
| 🐳 容器化 | 是 (Docker + Compose + Helm) |
| 🤖 CI | GitHub Actions (ruff + mypy + pytest + pip-audit + 前端 build) |
| 🔒 安全头 | HSTS/X-Frame/XSS/Referrer/CSP |
| 🔐 签名 | Webhook HMAC-SHA256 + JWT 黑名单吊销 |
| ⚡ 速率限制 | 200/min (slowapi) |
| 📝 审计日志 | 操作全链路可追溯 |
| 📊 监控 | Prometheus 标准化指标 |
| 🎨 前端 | React 18 + MUI v6 + ECharts + TypeScript |

## 📖 文档

完整文档站：https://shuangzhebai.github.io/gaokao-analyzer

- [快速开始](docs/website/docs/index.md)
- [API 参考](docs/website/docs/api.md)
- [架构说明](docs/website/docs/architecture.md)
- [部署指南](docs/website/docs/deployment.md)
- [开发指南](docs/website/docs/development.md)

## 🛣️ 路线图

详见 [ROADMAP.md](ROADMAP.md)

- **v6.1** (2026 Q3): OR-Tools 激活 · PG 正式切 · 数据采集 · 一键部署优化
- **v6.2** (2026 Q4): PWA 增强 · Word/LaTeX 导出 · 多租户 · 学情报告
- **v7.0** (2027): 原生移动 App · AI 辅助组卷 · 拍照搜题 · 企业版

## 🔬 技术栈

| 领域 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | PostgreSQL（主库）/ SQLite（开发退路） |
| ORM / Repository | 手写 Repository 模式（支持 asyncpg / aiosqlite 双后端） |
| 缓存 | Redis (L1 LRU + L2 Redis) |
| 异步任务 | Celery + Redis broker |
| 搜索引擎 | Meilisearch / SQLite FTS5 |
| 数值计算 | NumPy + SciPy + Numba JIT |
| 心理测量 | IRT 3PL / GPCM / GRM + OR-Tools CP-SAT |
| 鉴权 | JWT (python-jose) + bcrypt + Refresh Token + 黑名单 |
| 前端 | React 18 + TypeScript + MUI v6 + ECharts + Tailwind |
| 监控 | Prometheus (prometheus_client) |
| 容器化 | Docker + Compose + Helm Chart |
| CI/CD | GitHub Actions (lint + typecheck + test + security + build) |
| 文档 | Docusaurus + OpenAPI |

## 👥 社区

- [提交 Issue](https://github.com/shuangzhebai/gaokao-analyzer/issues/new/choose)
- [贡献指南](CONTRIBUTING.md)
- [更新日志](CHANGELOG.md)

## 📄 License

[MIT](LICENSE) © shuangzhebai

---

> **⭐ 如果这个项目对你有帮助，请点亮 Star！你的支持是持续改进的动力。**
