# Changelog

## v5.2.0 (2026-07-08)

### P0 — 工程优化基线
- **三层架构重构**：新建 repositories/ DAO 层 + services/ 业务层，路由层零裸 SQL
- **操作审计日志**：audit_log 表 + 中间件，POST/PUT/DELETE 自动记录
- **测试覆盖率 50%+**：21 → 130 测试函数，5 核心模块均 ≥ 50% 行覆盖率
- **mypy strict 类型注解**：47 源文件零错误
- **API 版本化 + JWT+RBAC + CORS 白名单**：/api/ + /api/v1/ 双路径兼容

### P1 — 性能与可扩展性
- **Redis 双级缓存**：L1 LRU + L2 Redis，无 Redis 时自动降级
- **Celery 异步任务**：analyze/simulate/collect 转为后台执行 + 状态轮询
- **分析器插件化**：BaseAnalyzer 抽象基类 + AnalyzerRegistry + 6 维度独立插件
- **i18n 国际化**：locales/zh.json + en.json + i18n.js 前端切换
- **Numba JIT 加速**：模拟核心循环 `@njit` 加速，无 Numba 时自动降级

### 工程基线（前期已落地）
- Docker 化（Dockerfile + docker-compose.yml）
- pre-commit 配置（ruff/black/mypy）
- CI 流水线（GitHub Actions）
- 安全头（HSTS / X-Content-Type-Options / X-Frame-Options / Referrer-Policy）
- API 速率限制（slowapi 200/min）
- 运行时上下文集中化（app.state.ctx）

_For full commit history, see [GitHub](https://github.com/shuangzhebai/gaokao-analyzer/commits/main)._
