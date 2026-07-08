---
sidebar_position: 5
---

# 开发

## 环境搭建

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt -r requirements-dev.txt
```

## 代码风格

本项目使用 ruff + black 统一格式（line-length=100）：

```bash
pip install -r requirements-dev.txt pre-commit
pre-commit install
pre-commit run --all-files
```

## 测试

```bash
pytest tests/ -q                    # 179 passed
pytest tests/ --cov --cov-report=term-missing  # 覆盖率
```

## 类型检查

```bash
mypy --strict app.py
```

## 项目结构

```
gaokao-analyzer/
├── app.py                  # FastAPI 装配
├── config.py               # 配置（科目/IRT/爬虫/权重/缓存）
├── models.py               # 数据库模型 + 迁移 + get_db
├── deps.py                 # 依赖注入
├── lifespan.py             # 生命周期管理
├── routes/                 # HTTP 路由
│   ├── papers.py           # 试卷 CRUD + 分析
│   ├── search.py           # 搜索
│   ├── auth.py             # 注册/登录
│   ├── audit.py            # 真实性审核
│   ├── scrape.py           # 采集
│   ├── analysis.py         # 分析报告
│   ├── dedup.py            # 查重
│   ├── tasks.py            # Celery 任务状态
│   └── official_docs.py    # 官方文件库
├── services/               # 业务层
│   ├── paper_service.py    # 试卷业务
│   ├── analysis_service.py # 分析业务
│   ├── auth_service.py     # JWT+密码
│   ├── cache_service.py    # Redis 缓存
│   ├── scrape_service.py   # 采集业务
│   ├── audit_service.py    # 审计日志
│   └── filter_service.py   # 筛选元数据
├── repositories/           # DAO 层
│   ├── paper_repo.py       # papers 表
│   ├── question_repo.py    # questions 表
│   ├── analysis_repo.py    # 分析结果
│   ├── audit_repo.py       # 审计日志
│   ├── search_repo.py      # FTS5 搜索
│   └── user_repo.py        # 用户/角色
├── analyzers/              # 可插拔分析器
│   ├── __init__.py         # BaseAnalyzer + Registry
│   └── impl.py             # 6 维度实现
├── tasks/                  # Celery 任务
├── static/                 # 前端 (SPA)
├── tests/                  # 测试 (179 tests)
└── locales/                # i18n (zh/en)
```
