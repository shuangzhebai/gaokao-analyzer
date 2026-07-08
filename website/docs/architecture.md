---
sidebar_position: 2
---

# 架构

## 分层架构

```
routes/  (HTTP 编排)  →  services/  (业务层)  →  repositories/  (DAO 层)  →  SQLite
                              ↕
                         engines/  (算法引擎)
                              ↕
                     celery_app/  (异步任务)
                              ↕
                         Redis (缓存 + broker)
```

## 数据流：试卷分析

```
Client → routes/papers.py → services/analysis_service.py
  → repositories/paper_repo.py (获取试卷)
  → engines/irt_model.py (IRT 参数估计)
  → engines/simulator.py (蒙特卡洛模拟)
  → engines/quality_analyzer.py (6 维度质量分析)
  → repositories/analysis_repo.py (存储结果)
  → JSON Response → Client
```

## 技术栈

| 层 | 技术 | 选型理由 |
|----|------|---------|
| Web 框架 | FastAPI | 异步原生、自动 OpenAPI、Pydantic 校验 |
| 数据库 | SQLite (WAL 模式) | 零运维、WAL 模式支持并发读写 |
| 缓存 | Redis (L1 LRU + L2 Redis) | 分布式缓存，无 Redis 自动降级 |
| 异步任务 | Celery + Redis broker | 长耗时不阻塞 API |
| 搜索引擎 | Meilisearch + FTS5 降级 | 中文分词、模糊纠错、高亮 |
| 鉴权 | JWT (python-jose) + API Key 兼容 | 双模式、静默降级 |
| 数值计算 | NumPy + Scipy + Numba (可选) | 向量化 + JIT 加速 |
| 容器化 | Docker + Docker Compose | 一次构建到处运行 |
