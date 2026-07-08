# gaokao-analyzer — 高考模拟卷智能分析系统

> IRT 3PL 参数估计 · 蒙特卡洛模拟 · 6 维度质量分析 · DeepSeek 真实性审核 · 知识点映射 · 爬虫采集

---

## 📋 目录

- [项目简介](#项目简介)
- [快速开始](#快速开始)
- [架构](#架构)
- [API 概览](#api-概览)
- [开发指南](#开发指南)
- [版本发布](#版本发布)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## 项目简介

gaokao-analyzer 是一款面向高考教研场景的智能试卷分析系统，基于 IRT（项目反应理论）和蒙特卡洛模拟技术，对模拟试卷进行多维度量化评估。核心算法引擎达到 NCME 测量标准学术水准。

**核心能力**
- **IRT 能力估计** — 3PL 模型参数估计（难度/区分度/猜测参数）
- **蒙特卡洛模拟** — 10 万考生成绩分布模拟 + 偏态校准
- **6 维度质量分析** — 难度/区分度/信度/效度/知识点覆盖/题型分布
- **DeepSeek 真实性审核** — AI 验证试卷来源与内容真实性
- **多源爬虫采集** — 可插拔适配器架构
- **官方文档库** — 教育部政策文件/课标/考试公告

## 快速开始

### Docker 部署（推荐）

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer

# 启动（web + redis + celery worker）
docker compose up -d

# 访问 http://localhost:8000
```

首次启动后注册管理员用户：
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -d "username=admin&password=P@ssw0rd&role=admin"
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -d "username=admin&password=P@ssw0rd"
# 使用返回的 token 调用 API
```

### 本地开发

```bash
# 环境要求：Python 3.13+
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000

# 运行测试
pip install -r requirements-dev.txt
pytest tests/ -q  # 179 passed
```

## 架构

```
routes/  (HTTP 编排)  →  services/  (业务层)  →  repositories/  (DAO 层)  →  SQLite
                              ↕
                         engines/  (算法引擎)
                              ↕
                     celery_app/  (异步任务)
                              ↕
                         Redis (缓存 + broker)
```

## API 概览

所有端点支持 `/api/v1/*` 与旧路径 `/api/*` 兼容。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/register` | POST | 注册用户 |
| `/api/v1/auth/login` | POST | 登录获取 JWT |
| `/api/v1/papers` | GET | 试卷列表 |
| `/api/v1/papers/{id}` | GET | 试卷详情 |
| `/api/v1/papers/upload` | POST | 上传试卷 |
| `/api/v1/papers/{id}/simulate` | POST | 成绩模拟 |
| `/api/v1/search` | GET | 搜索（FTS5） |
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/tasks/{id}` | GET | Celery 任务状态 |

完整 API 文档：启动后访问 `/docs`（OpenAPI Swagger UI）。

## 开发指南

### 代码风格

本项目使用 ruff + black 统一格式：
```bash
pip install -r requirements-dev.txt pre-commit
pre-commit install
pre-commit run --all-files
```

### 测试

```bash
pytest tests/ -q                    # 179 passed
pytest tests/ --cov=services --cov-report=term-missing  # 覆盖率
```

### CI

每次 push 自动触发 GitHub Actions：
- `ruff check .` — 代码风格检查
- `black --check .` — 格式检查
- `mypy --strict app.py` — 类型检查
- `pytest tests/ -q` — 测试

## 版本发布

当前版本：v5.2.0（[Release Notes](https://github.com/shuangzhebai/gaokao-analyzer/releases/tag/v5.2.0)）

版本号遵循 [SemVer](https://semver.org/)：
- v5.Y.Z — 工程优化/重构（不改变 API 契约）
- v5.2.x — 补丁/缺陷修复
- v6.0.0 — 重大架构变更/API 不兼容

## 贡献指南

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与贡献。

### 报告问题

- [新建 Bug 报告](https://github.com/shuangzhebai/gaokao-analyzer/issues/new?template=bug_report.md)
- [新建功能请求](https://github.com/shuangzhebai/gaokao-analyzer/issues/new?template=feature_request.md)

## 许可证

[MIT](LICENSE) © shuangzhebai
