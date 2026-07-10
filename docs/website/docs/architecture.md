---
sidebar_position: 2
---

# 架构

## 四层模块化架构（v6.0）

```
                    ┌─────────────────────────┐
                    │  前端 (React + ECharts)  │
                    │  /questions  /quality    │
                    │  /composition  /errors   │
                    │  学生/教师/教研员工作台    │
                    └─────┬───────────────────┘
                          │ REST API (74 端点)
                    ┌─────▼───────────────────┐
                    │  FastAPI 路由层           │
                    │  questions / quality     │
                    │  composition / errors    │
                    │  collection / auth 等    │
                    └─────┬───────────────────┘
                    ┌─────▼───────────────────┐
                    │  服务编排层               │
                    │  QuestionService         │
                    │  QualityService          │
                    │  CompositionService      │
                    │  ErrorService            │
                    │  CollectionService ...   │
                    └──┬──────────┬───────────┘
                       │          │
              ┌────────▼──┐  ┌───▼───────────┐
              │ 引擎层     │  │ 数据访问层      │
              │ IRT 3PL/   │  │ Repository 模式 │
              │ GPCM/GRM   │  │ PG / SQLite    │
              │ 题型分类    │  │ 双后端抽象      │
              │ 质量诊断    │  │                │
              │ OR-Tools   │  │                │
              └────────────┘  └───────────────┘
                       │              │
              ┌────────▼──────────────▼──────┐
              │  基础设施                     │
              │  PostgreSQL / SQLite          │
              │  Redis + Celery              │
              │  Meilisearch                 │
              │  Prometheus                  │
              └──────────────────────────────┘
```

## v6.0 新模块数据流

### 题型分类流
```
试卷/题目 → QuestionClassifier.extract_features()
  → 规则引擎分类（选项数/填空标记/解题关键词）
  → QuestionService.classify_and_save()
  → QuestionRepository → questions 表 + question_types 表
```

### 质量诊断流
```
题目 ID → HybridQualityEngine.compute_ctt_indicators() [p值/区分度/双列相关]
  + → IRT 引擎预计算缓存 [a/b/c/CFI/TLI/RMSEA]
  → generate_6d_report() [难度/区分度/信度/效度/知识点/题型]
  → QualityReport (ECharts 雷达图)
```

### 智能组卷流
```
约束条件（学科/难度/题型/知识点）
  → CompositionEngine.solve()
    [OR-Tools CP-SAT: IntVar + 硬约束 + 目标函数]
  → 质量预检报告 → 预览 → 微调 → 导出(PDF)
```

### 错题闭环流
```
错题录入 → ErrorService.record_error()
  → StudentProfileService.update_knowledge_mastery()
  → diagnose_weakness() [IRT θ + 知识图谱]
  → recommend_similar() [同知识点+IRT参数相似度]
```

## 技术栈

| 层 | 技术 | 选型理由 |
|----|------|---------|
| Web 框架 | FastAPI | 异步原生、自动 OpenAPI、Pydantic 校验 |
| 数据库 | PostgreSQL（主库）/ SQLite（开发退路） | PG 支撑校园级并发；SQLite 本地零运维 |
| Repository 模式 | 手写 BaseRepository 抽象 | 双后端统一接口，支持 asyncpg / aiosqlite |
| 缓存 | Redis (L1 LRU + L2 Redis) | 分布式缓存，无 Redis 自动降级 |
| 异步任务 | Celery + Redis broker | 长耗时不阻塞 API |
| 搜索引擎 | Meilisearch + FTS5 降级 | 中文分词、模糊纠错、高亮 |
| 心理测量 | IRT 3PL / GPCM / GRM | 竞品全部基于 CTT，本系统独有 |
| 约束求解 | OR-Tools CP-SAT | 智能组卷多目标优化 |
| 鉴权 | JWT + Refresh Token + 黑名单 | 吊销 + 轮换机制 |
| 数值计算 | NumPy + SciPy + Numba JIT | 向量化 + JIT 加速 |
| 前端 | React 18 + TypeScript + MUI v6 + ECharts | 类型安全 + 丰富组件 + 高性能图表 |
| 监控 | Prometheus (prometheus_client) | 标准化指标，可对接 Grafana |
| 容器化 | Docker Compose + Helm Chart | 本地/生产/ K8s 多模式 |
| 部署 | GitHub Actions CI/CD | mypy/pytest/pip-audit/frontend-build |
