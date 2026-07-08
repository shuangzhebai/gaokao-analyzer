# gaokao-analyzer × 世界顶级同类软件 · 七维差距分析

> 分析日期：2026-07-08
> 分析方式：主理人齐活林（Qi）实地读代码 + 配置核查产出（注：本轮 `software-product-manager` 等子 agent 在会话层无法启动，分析由主理人基于真实代码状态汇总，非成员独立产出）
> 当前版本：`config.VERSION = "5.1"`，已推送 GitHub（`github.com/shuangzhebai/gaokao-analyzer`，main @ cb39b56）

## 总览

gaokao-analyzer 的**算法引擎已处于世界第一梯队**：IRT 3PL 参数估计 + 10 万考生蒙特卡洛模拟 + 6 维度质量分析 + 知识点映射 + 试卷查重 + DeepSeek 真实性审核 + 官方文档库 + 地区层级 + 真实成绩校准数据 + 可插拔爬虫适配器。其测量方法论与美国 NCME 标准、TestAnaAPP 学术水准处于同一水平线。

**差距集中在「工程化包装层」**：缺少三层架构、测试覆盖、类型安全、现代鉴权体系、分布式缓存/异步任务、国际化、文档站与社区运营。这些缺口拼的不是算法研究，而是工程量，**投入产出比最高**。

### 一句话结论

> 算法已达世界级，工程化是短板；补齐「分层架构 + 测试 + 类型 + 鉴权 + 缓存/异步 + i18n + 文档社区」这七块，即可从「个人强工具」跃迁为「可规模化服务的产品」。

### 优先级路线图（对照上次 P0/P1/P2/P3，更新状态）

| 阶段 | 关键项 | 状态 | 工作量估算 |
|------|--------|------|-----------|
| 🚨 P0 工程基线 | Docker 化 / pre-commit / CI / 安全头 / 限速 / 上下文集中化 | ✅ **已完成**（2026-07-07 合并） | — |
| 🔴 P1 近期做 | 测试覆盖 50%+ / 三层架构拆分 / mypy strict 类型 / API 版本化 / **操作审计日志** / JWT·RBAC+CORS 白名单 | ⬜ 未开始 | ~4 天 |
| 🟡 P2 中期做 | Redis 缓存 / Celery 异步 / 分析器插件化 / i18n / Numba JIT | ⬜ 未开始 | ~3.5 天 |
| 🟢 P3 长期做 | PWA / 多租户 / 文档站 / Meilisearch / 社区开源 / SemVer 发布 / 在线 Demo | ⬜ 未开始 | ~4 天 |

---

## ① 功能完整性（Functional Completeness）

**对标基准**：TestAnaAPP / NCME 测量标准平台、商用组卷阅卷系统（学科网、菁优网）、Canvas/Blackboard 教育分析模块。

**当前状态（已查证）**
- 后端提供：IRT 估计（`irt_model`）、蒙特卡洛模拟（`simulator`，`MC_CONFIG.n_students=100000`）、6 维度质量分析（`ANALYSIS_WEIGHTS`）、知识点映射、查重（`dedup`）、DeepSeek 真实性审核（`auto_scraper.CrossVerifier`）、官方文档库（`official_docs`）、地区层级校验（`REGION_HIERARCHY`）、真实成绩校准（`CALIBRATION_DATA`）、可插拔爬虫适配器（`SCRAPER_ADAPTER_TYPES` + `AdapterRegistry`）、等级赋分（`GRADE_ASSIGNMENT_RULES`）、课标/素养分析。
- 前端有仪表盘页（`/api/dashboard` + tab-item dashboard）、文件库页、采集页。

**存在不足**
- 🟡 中等：报告**导出/分享**能力弱——分析报告仅在浏览器内渲染（HTML 视图），无 PDF/Word/图片一键导出，难以流转。
- 🟡 中等：**无用户体系与历史**——仅 API Key 鉴权，无账号，用户无法保存/回溯自己的分析任务。
- 🟡 中等：**无协作批注**——不支持多人同时分析、批注、评论（对标 Notion/Google Docs 协作）。
- 🟢 轻微：题型覆盖偏向 choice/fill/solve，**主观题/作文的自动化评分**能力有限。
- 🟢 轻微：跨试卷**趋势/对比分析**已搭仪表盘骨架，但维度聚合（时间序列、学校维度对比）还不够深。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| 报告导出：前端 `window.print()` + 后端 `reportlab`/HTML→PDF | 1 天 | 成果可流转，最直接的用户价值 |
| 用户体系（JWT + 用户表 + 分析任务历史） | 2 天 | 留存与个性化，也为多租户铺路 |
| 协作批注（评论表 + 批注 API） | 2 天 | 教研组场景刚需 |

---

## ② 性能表现（Performance）

**对标基准**：FastAPI 性能优化原则、Redis 多级缓存、异步并发、Numba/Rust(JIT)、专职搜索引擎（Meilisearch/Elasticsearch）。

**当前状态（已查证）**
- `ANALYSIS_CONFIG.use_cache=True`（进程内 LRU 缓存 IRT 拟合/知识点映射）；`max_workers=4` 线程池释放 GIL；numpy 矢量化；`MC_CONFIG.n_students=100000` 蒙特卡洛。
- 搜索基于 SQLite FTS5（配置在 `search` 引擎）。
- 前端为单文件 `static/index.html`，Chart.js 内联。

**存在不足**
- 🟡 中等：蒙特卡洛/IRT 为**纯 numpy CPU 计算**，无 JIT（Numba/PyO3）。瓶颈明显，模拟速度可提升 5–20 倍。
- 🟡 中等：**无分布式缓存**（全仓无 redis/celery/memcached/aiocache）——LRU 仅进程内，多 worker/多进程间不通，重复分析每次重算。
- 🟡 中等：搜索用 **SQLite FTS5**，中文分词/模糊纠错/高亮片段/聚合统计远弱于 Meilisearch。
- 🟡 中等：**耗时分析端点同步执行**（`/api/papers/{id}/simulate` 等），无 Celery 异步；高负载会阻塞 API（采集端点已用 `BackgroundTasks`，但分析未用）。
- 🟢 轻微：前端无代码分割/CDN/Brotli，首屏 JS 体积偏大。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| Numba `@njit` 加速 simulator/IRT 热循环 | 0.5 天 | 模拟 5–20× |
| Redis 缓存分析报告/FTS 结果（TTL 5min） | 0.5 天 | 重复请求毫秒级 |
| Celery+Redis 把 analyze/simulate/collect 转异步 + 进度轮询 | 1.5 天 | API 不阻塞 |
| FTS5 → Meilisearch（中文+纠错+高亮） | 1 天 | 搜索体验接近百度 |

---

## ③ 用户体验（UX）

**对标基准**：shadcn/ui + Radix UI、Ant Design / Vercel 设计语言、WCAG 2.2 AA、PWA。

**当前状态（已查证）**
- `static/index.html`：液态玻璃风格、底部 Tab 导航（`tab-item`）、已加 toast 错误反馈、`/api/dashboard` 仪表盘页、语义标签 `<nav class="navbar">` / `<button>`（非 `div onclick`，良好）。
- `lang="zh-CN"` 已设。

**存在不足**
- 🟡 中等：**无统一设计系统**——颜色/字距/间距/动效无规范 token（无 shadcn/Radix），各组件样式散落。
- 🟡 中等：**无 PWA**——无 `manifest.json` / Service Worker，不可安装、不可离线。
- 🟡 中等：**可访问性缺失（WCAG 2.2 AA）**——全仓无 `aria-label`/`role`，无键盘导航顺序验证，对比度未检查；仍用 `confirm()`（与 toast 体系不一致）。
- 🟢 轻微：交互动效无统一 300ms 规范。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| 引入轻量设计 token（CSS 变量统一色板/间距/动效 300ms） | 0.5 天 | 一致性↑ |
| PWA：manifest + SW + 离线缓存 | 0.5 天 | 可安装/离线 |
| a11y：aria-label 全量 + 键盘导航 + 替换 confirm 为自定义对话框 | 1 天 | 屏幕阅读器可用 |
| 语义化 + 对比度校验 | 0.5 天 | 视障可读、SEO↑ |

---

## ④ 代码架构（Architecture）

**对标基准**：FastAPI Best Architecture（router→service→repository 三层）、DDD、事件驱动、API 版本化、插件化。

**当前状态（已查证）**
- ✅ 干净的依赖注入：`lifespan.py` 注入 14 个引擎单例到 `app.state.*`，`deps.py` 的 `get_*` 取用；新增 `app.state.ctx`（`app_context.py`）集中运行时上下文。
- ✅ 引擎与 HTTP 分离：业务逻辑在 `irt_model`/`quality_analyzer`/`simulator` 等引擎模块。
- ✅ 爬虫**可插拔**：`AdapterRegistry` + `SCRAPER_ADAPTER_TYPES` + 配置驱动数据源。
- ⚠️ 但 `routes/audit.py:49` 直接 `UPDATE papers SET ...` 裸 SQL；`routes/papers.py` 多处裸 SQL 与编排逻辑共存。

**存在不足**
- 🟡 中等：**无三层架构**——路由层既做 HTTP 编排又直接写库（裸 SQL），缺 `services/`（业务）与 `repositories/`（DAO）抽象，DB schema 与路由耦合。
- 🟡 中等：**无 API 版本化**（`/api/v1/` 缺失），升级有破坏客户端风险。
- 🟡 中等：**分析器未插件化**——6 维度硬编码于 `ANALYSIS_WEIGHTS`，无 `BaseAnalyzer` 注册表（爬虫可插拔，分析器不可）。
- 🟡 中等：**类型覆盖低**——无 `mypy --strict`，大量函数缺类型注解。
- 🟢 轻微：无事件驱动/异步任务框架（与性能项重叠）。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| 抽 `repositories/`（DAO）+ `services/`（业务），路由只编排 | 2–3 天 | 可测试性/维护性↑↑ |
| `mypy --strict` + 补类型注解 | 1 天 | 运行时类型错↓90% |
| API 版本化 `/api/v1/` | 0.3 天 | 安全迭代 |
| `BaseAnalyzer` 注册表，维度可插拔 | 1 天 | 用户可扩展分析 |

---

## ⑤ 安全性（Security）

**对标基准**：OWASP Top 10、JWT/OAuth2/RBAC、操作审计日志、严格 CORS 白名单、HSTS。

**当前状态（已查证）**
- ✅ API Key 鉴权中间件（`AuthMiddleware`）。
- ✅ 安全头已加（`app.py` T4）：`Strict-Transport-Security` / `X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy: no-referrer`。
- ✅ slowapi 全局限速 `200/minute`（未装时优雅降级，见 T5）。
- ✅ FTS 注入已过滤；CSP 头（前序版本已加）。
- ⚠️ **重要更正**：`routes/audit.py` 的「audit」是**试卷真实性审核/交叉验证**（`AuthVerifier`/`CrossVerifier`），**不是操作审计日志**。

**存在不足**
- 🟡 中等：**无现代鉴权体系**——单一共享 API Key，无 JWT/OAuth2/RBAC，无法做资源级隔离（多用户不安全）。
- 🟡 中等：**CORS 仍为 `*` 通配**（`CORS_ORIGINS` 默认 `*`），无严格来源白名单。
- 🟡 中等：**操作审计日志缺失**——无「谁/何时/做了什么」的全链路记录（原报告该项缺口**仍未补**）。
- 🟢 轻微：限速粒度粗（全局 200/min，登录/提交类未更严），且仅 slowapi 安装后生效。
- 🟢 轻微：密钥仅靠环境变量（`DEEPSEEK_API_KEY`），无 Vault/密钥管理。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| JWT + RBAC（用户/角色/资源权限） | 2 天 | 多用户安全隔离 |
| CORS 严格白名单（环境变量来源列表） | 0.2 天 | 防跨站 |
| 操作审计表 `audit_log(user,action,resource_id,ip,ts)` | 0.5 天 | 全链路可追溯 |
| 分端点限速（登录/提交更严）+ 装 slowapi | 0.3 天 | 防暴力 |

---

## ⑥ 可扩展性（Scalability / Extensibility）

**对标基准**：插件系统（VSCode/WP）、微服务、多租户 SaaS、API 版本管理、读写分离。

**当前状态（已查证）**
- ✅ 爬虫数据源可插拔（`AdapterRegistry` + 配置驱动 `DATA_SOURCES`）。
- ✅ 配置惰性 getter（`get_analysis_config()` 等），运行时可调参。
- ✅ 已 Docker 化（单 `web` 服务，compose 挂载 `./data`）。

**存在不足**
- 🟡 中等：**分析器不可插拔**（6 维度硬编码，用户无法自定义维度/权重）。
- 🟡 中等：**无多租户**——无 `tenant_id`，单实例无法安全服务多校/多机构。
- 🟡 中等：**单进程 SQLite**——写锁是高并发硬天花板；无读写分离、无连接池（仅 aiosqlite 单连接风格）。
- 🟢 轻微：无 API 版本化（见架构项）；无水平扩展/微服务。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| `BaseAnalyzer` 插件化 + 权重可调 | 1 天 | 用户自定义分析 |
| 多租户：`tenant_id` + 路由注入 | 1 天 | 一实例服务多校 |
| PostgreSQL + 读写分离 + 连接池（SQLAlchemy 2.0） | 2 天 | 破除并发天花板 |
| API 版本化 `/api/v1/` | 0.3 天 | 兼容迭代 |

---

## ⑦ 生态系统支持（Ecosystem）

**对标基准**：i18next、Stripe 级文档体系（Docusaurus/GitBook）、Vue.js/ FastAPI 社区运营、SemVer 发布、PyPI。

**当前状态（已查证）**
- ✅ 已上 GitHub（公开仓库，2026-07-07 推送）。
- ✅ CI 就位（`.github/workflows/ci.yml`：ruff/black/mypy/pytest）。
- ✅ FastAPI 自动 OpenAPI；有 `README.md` / `overview.md` / `OPTIMIZATION_LOG.md`。
- ⚠️ 全仓**无 i18n**（无 locale/Intl/i18next，中文硬编码）。

**存在不足**
- 🟡 中等：**零国际化**——仅中文，非中文场景完全不可用（对标 i18next + 10+ 语言）。
- 🟡 中等：**无文档站**——无 Docusaurus/GitBook，无定制 OpenAPI 描述、无 CHANGELOG、无部署指南/FAQ。
- 🟡 中等：**无社区运营基础**——无 `CONTRIBUTING.md` / Issue/PR 模板 / Code of Conduct（虽已公开，但无参与渠道）。
- 🟡 中等：**无版本发布**——无 SemVer tag / GitHub Release / PyPI 包。
- 🟢 轻微：无在线 Demo / 预置样例数据集（用户无法零配置体验）。

**改进方向**
| 方向 | 工作量 | 收益 |
|------|--------|------|
| i18next：抽取文案到 `locales/zh.json`+`en.json` | 1 天 | 中英文切换 |
| Docusaurus 文档站 + 定制 OpenAPI + CHANGELOG | 1.5 天 | 降低使用门槛 |
| CONTRIBUTING + Issue/PR 模板 + SemVer Release | 0.5 天 | 外部贡献可参与 |
| 在线 Demo（Vercel+Railway）+ 30 份样例卷 | 1 天 | 零配置体验 |

---

## 优先级矩阵（维度 × 严重度 × 工作量 × 建议阶段）

| 维度 | 最严重缺口 | 严重度 | 工作量 | 建议阶段 |
|------|-----------|--------|--------|----------|
| 功能完整性 | 报告导出 / 用户体系 | 中 | 1–2 天 | P1/P3 |
| 性能表现 | JIT / 分布式缓存 / 异步 | 中 | 0.5–1.5 天 | P2 |
| 用户体验 | 设计系统 / PWA / a11y | 中 | 0.5–1 天 | P3 |
| 代码架构 | 三层架构 / 类型 / 版本化 | 中 | 1–3 天 | P1 |
| 安全性 | JWT·RBAC / CORS 白名单 / **操作审计日志** | 中 | 0.2–2 天 | P1 |
| 可扩展性 | 分析器插件 / 多租户 / PG | 中 | 1–2 天 | P2/P3 |
| 生态系统 | i18n / 文档站 / 社区 / 发布 | 中 | 0.5–1.5 天 | P3 |

> **投入最小、收益最大的下一步（推荐顺序）**：
> 1. 测试覆盖率补到 50%+（重构底气，~2 天）
> 2. 三层架构拆分 services/repositories（维护性飞跃，~2–3 天）
> 3. mypy strict 类型 + API 版本化（质量与兼容，~1.3 天）
> 4. 操作审计日志 + CORS 白名单（安全兜底，~0.7 天）
> 之后进入 P2：Redis 缓存 + Celery 异步 + 分析器插件 + i18n。

---

## 附录：本分析的事实依据（已查证文件）

- `app.py`：中间件顺序 CORS→Auth→安全头→slowapi→路由；`audit.router` 实为真实性审核。
- `config.py`：领域配置极丰富（IRT/MC/校准/地区/题型/等级赋分/数据源适配器），鉴权仅 API Key，无 JWT/RBAC。
- `routes/*.py`：业务编排与裸 SQL 共存（如 `audit.py:49` `UPDATE papers`），无 services/repositories。
- `static/index.html`：单文件 SPA，语义标签尚可，无 aria/role、无 PWA、中文硬编码、`confirm()` 仍用。
- `tests/`：仅 15 个测试函数（analysis 9 + 安全头 4 + 限速 2），业务覆盖率 <5%。
- 全仓无 redis/celery/memcached/aiocache、无 i18n/locale/Intl。
- 已落地 P0：`Dockerfile`/`docker-compose.yml`/`.pre-commit-config.yaml`/`pyproject.toml`/`requirements-dev.txt`/`.github/workflows/ci.yml`/`app_context.py` + 安全头 + slowapi 限速。
