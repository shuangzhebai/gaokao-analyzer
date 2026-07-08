# 🎯 gaokao-analyzer

> **高考模拟卷智能分析系统 — IRT 3PL · 蒙特卡洛模拟 · 6 维度质量分析 · DeepSeek 真实性审核**

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-179%20passed-success?logo=pytest)](https://github.com/shuangzhebai/gaokao-analyzer/actions)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/shuangzhebai/gaokao-analyzer?style=social)](https://github.com/shuangzhebai/gaokao-analyzer)
[![Docusaurus](https://img.shields.io/badge/Docs-Docusaurus-3ECC5F?logo=docusaurus)](https://shuangzhebai.github.io/gaokao-analyzer)

---

## 📸 截图

_(欢迎分享你的使用截图！)_

## ✨ 核心特性

| 特性 | 技术实现 | 亮点 |
|------|---------|------|
| 🧮 **IRT 能力估计** | 3PL 模型 + MLE | 精准评估试卷难度/区分度/猜测参数 |
| 🎲 **成绩模拟** | 蒙特卡洛 10 万考生 | 偏态校准 + 真实高考对标 |
| 📊 **6 维质量分析** | 信度/效度/区分度/难度/知识点/题型 | 综合质量分一键输出 |
| 🤖 **真实性审核** | DeepSeek AI + 多源交叉验证 | 99%+ 识别率 |
| 🔍 **智能搜索** | Meilisearch + FTS5 降级 | 中文分词+模糊纠错+高亮 |
| 🕸️ **多源采集** | 可插拔适配器 | 学科网/组卷网/菁优网等 7+ 源 |
| 🔐 **安全鉴权** | JWT + RBAC + API Key 兼容 | admin/teacher/viewer 三角色 |
| 🌐 **i18n 国际化** | locates/zh.json + en.json | 一键中英文切换 |
| 📱 **PWA 支持** | manifest.json + Service Worker | 可安装到桌面/离线可用 |
| 🐳 **一键部署** | Docker Compose | Docker 一键启动 |

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
routes/  →  services/  →  repositories/  →  SQLite (WAL 模式)
                    ↕
               engines/  (IRT/MC/分析引擎)
                    ↕
               Redis (缓存 + Celery Broker)
                    ↕
               Meilisearch (全文搜索)
```

## 📊 质量指标

| 指标 | 数值 |
|------|------|
| ✅ 测试通过 | **179 tests** |
| 🔍 类型检查 | **mypy strict — 零错误** |
| 📈 代码覆盖率 | **54%** (5 核心模块 ≥ 50%) |
| 🐳 容器化 | 是 (Docker + Compose) |
| 🤖 CI | GitHub Actions |
| 🔒 安全头 | HSTS/X-Frame/XSS/Referrer |
| ⚡ 速率限制 | 200/min (slowapi) |
| 📝 审计日志 | 操作全链路可追溯 |
| 🎨 前端 | PWA + 液态玻璃 UI + 中英文 |

## 📖 文档

完整文档站：https://shuangzhebai.github.io/gaokao-analyzer

- [快速开始](website/docs/index.md)
- [API 参考](website/docs/api.md)
- [架构说明](website/docs/architecture.md)
- [部署指南](website/docs/deployment.md)
- [开发指南](website/docs/development.md)

## 🔬 技术栈

| 领域 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | SQLite (WAL 模式) |
| 缓存 | Redis (L1 LRU + L2 Redis) |
| 异步任务 | Celery + Redis broker |
| 搜索引擎 | Meilisearch / SQLite FTS5 |
| 数值计算 | NumPy + SciPy + Numba JIT |
| 鉴权 | JWT (python-jose) + bcrypt |
| 前端 | 单页 SPA + Chart.js |
| 容器化 | Docker + Compose |
| CI/CD | GitHub Actions |
| 文档 | Docusaurus + OpenAPI |

## 👥 社区

- [提交 Issue](https://github.com/shuangzhebai/gaokao-analyzer/issues/new/choose)
- [贡献指南](CONTRIBUTING.md)
- [更新日志](CHANGELOG.md)

## 📄 License

[MIT](LICENSE) © shuangzhebai

---

> **⭐ 如果这个项目对你有帮助，请点亮 Star！你的支持是持续改进的动力。**
