# gaokao-analyzer 工程优化 PRD（P0/P1/P2 完整路线图）

> **文档状态**：定稿  
> **编写人**：Alice（Product Manager）  
> **编写依据**：`docs/benchmark-analysis-2026-07-08.md` + 代码结构现场确认  
> **当前版本**：v5.1，路径 `C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer`

---

## 1. 产品目标

**一句话描述**：将 gaokao-analyzer 从「个人强工具」升级为「可规模化服务的产品」——通过补齐三层架构、测试覆盖率、类型安全、现代鉴权、缓存/异步、i18n、文档站与社区运营七块工程化短板，使算法引擎（IRT/MC/6维分析）的世界级能力得以在真实多用户生产环境中可靠运行。

---

## 2. 用户故事

| ID | As a（角色） | I want（需求） | So that（价值） |
|----|-------------|---------------|----------------|
| US-01 | 开发者 | 给 paper_analysis、scraper、search、IRT 引擎写单元测试 + 集成测试 | 重构时敢改代码，CI 门禁可拦截回归 |
| US-02 | 后端开发者 | 路由层只做 HTTP 编排，业务逻辑在 services/、数据访问在 repositories/ | 代码可读性↑、职责边界清晰、测试可 mock |
| US-03 | 开发者 | 所有函数有完整类型注解并通过 mypy --strict | 运行时类型错误↓90%，IDE 提示完整 |
| US-04 | 前端/API 调用方 | API 路径带 `/api/v1/` 版本前缀 | 后端升级时客户端不崩，平滑迁移 |
| US-05 | 管理员/审计员 | 每一位用户的敏感操作记录到 audit_log 表 | 安全合规，问题可追溯 |
| US-06 | 用户 | 登录后使用 JWT 令牌访问资源，不同角色有不同权限 | 多用户数据安全隔离，不再是共享 API Key |
| US-07 | 运维/开发者 | CORS 只允许配置的白名单来源 | 防跨站请求攻击 |
| US-08 | 高频用户 | 重复查询的分析报告/搜索结果毫秒级返回 | 体验流畅，不重复计算 |
| US-09 | 用户 | 耗时较长的分析/模拟/采集操作提交后可以离开，之后回来查看进度 | 不阻塞浏览器，大任务可后台完成 |
| US-10 | 管理员/教研员 | 自定义分析维度和权重，不用改代码 | 适配不同学校的评估标准 |
| US-11 | 非中文用户 | 切换界面语言为英文 | 产品可出口海外 |
| US-12 | 用户 | 大型模拟能更快完成 | 等待时间从分钟级降到秒级 |
| US-13 | 移动用户 | 在手机上安装为 PWA 应用，离线也能看已有报告 | 碎片时间可用，断网也能用 |
| US-14 | SaaS 平台运营者 | 一套部署服务多个学校/机构，数据天然隔离 | 安全+降低运维成本 |
| US-15 | 新用户 | 访问 Docusaurus 文档站，5 分钟内上手部署和使用 | 降低学习门槛 |
| US-16 | 搜索用户 | 输入错别字也能搜到结果，结果带高亮 | 中文搜索体验接近百度 |
| US-17 | 开源贡献者 | 看到 CONTRIBUTING.md 和 Issue/PR 模板 | 知道怎么参与贡献 |

---

## 3. 需求池

### 优先级说明

- **P0（必须做）**：≈ 原路线图 P1，约 4 天工作量。不做则系统不可上生产、不可多用户、不可安全运维。
- **P1（应该做）**：≈ 原路线图 P2，约 3.5 天工作量。不做则性能瓶颈明显、不可扩展、仅中文可用。
- **P2（可以做）**：≈ 原路线图 P3，约 4 天工作量。不做则缺乏移动端、多租户、文档站、社区引力。

### P0 需求（必须做，共 6 项）

#### P0-1：测试覆盖率提升到 50%+

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P0-01 |
| **优先级** | P0（Must） |
| **用户故事** | US-01 |
| **描述** | 补全核心模块的单元测试和集成测试，使整体行覆盖率 ≥ 50% |
| **涉及模块与文件** | `tests/test_analysis.py`（扩展）、**新建** `tests/test_paper_analysis.py`、`tests/test_scraper.py`、`tests/test_search.py`、`tests/test_irt.py`、`tests/test_simulator.py`；`paper_analysis.py`、`scraper.py`、`search.py`、`analyzer.py`、`simulator.py` |
| **验收标准** | • `pytest --cov=paper_analysis,scraper,search,analyzer,simulator --cov-report=term-missing` 行覆盖率 ≥ 50%<br>• 总测试函数数从当前 15 个增加到 ≥ 40 个<br>• 包括：正常路径、边界值、空输入、异常路径<br>• CI 门禁（`.github/workflows/ci.yml`）中 `pytest` 通过 |
| **依赖** | 无（可独立进行） |

#### P0-2：三层架构拆分（services/ + repositories/）

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P0-02 |
| **优先级** | P0（Must） |
| **用户故事** | US-02 |
| **描述** | 抽取 `services/`（业务层）和 `repositories/`（DAO 层），路由层只做 HTTP 编排。当前 `routes/*.py` 中的裸 SQL（如 `routes/papers.py` 大量 `db.execute()` 和 `db.execute_fetchall()`）全部迁移到 `repositories/`；业务编排逻辑（如分析流程的先后顺序、组合调用）迁移到 `services/`。 |
| **涉及模块与文件** | **新建** `services/` 目录 + `services/__init__.py`、`services/paper_service.py`、`services/analysis_service.py`、`services/scrape_service.py`、`services/search_service.py`；**新建** `repositories/` 目录 + `repositories/__init__.py`、`repositories/paper_repo.py`、`repositories/question_repo.py`、`repositories/analysis_repo.py`、`repositories/search_repo.py`；**修改** `routes/papers.py`、`routes/search.py`、`routes/analysis.py`、`routes/audit.py`、`routes/dedup.py`、`routes/scrape.py`、`routes/official_docs.py`（移除裸 SQL，调用 services）；`deps.py`（注册新服务依赖）；`app.py`（注册新依赖） |
| **验收标准** | • `routes/*.py` 中无直接 SQL（`db.execute()`/`db.execute_fetchall()`）<br>• 所有 DB 操作通过 `repositories/*.py` 方法完成<br>• 所有业务编排通过 `services/*.py` 方法完成<br>• 路由文件仅保留：参数校验、响应序列化、调用 service<br>• `pytest` 全部通过 |
| **依赖** | 建议在 P0-01（测试）之后或并行进行，测试提供重构安全感 |

#### P0-3：mypy strict 类型注解

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P0-03 |
| **优先级** | P0（Must） |
| **用户故事** | US-03 |
| **描述** | 为全量 Python 文件补全函数签名类型注解，在 `pyproject.toml` 中将 mypy 配置升级到 `--strict` 级别（当前为宽松模式：`ignore_missing_imports=true, exclude=["tests"]`） |
| **涉及模块与文件** | `pyproject.toml`（修改 `[tool.mypy]`）；所有 `.py` 源文件（`app.py`、`config.py`、`models.py`、`deps.py`、`lifespan.py`、`analyzer.py`、`paper_analysis.py`、`simulator.py`、`search.py`、`scraper.py`、`routes/*.py`、`edu_source_adapters.py` 等） |
| **验收标准** | • `mypy --strict src/`（或项目根目录）零错误通过<br>• 所有公共函数有完整参数类型 + 返回类型注解<br>• `pyproject.toml` 中移除 `ignore_missing_imports=true`，`exclude` 保留 `tests`（部分妥协） |
| **依赖** | 建议在 P0-02（三层架构）之后进行，避免因文件重构反复改注解 |

#### P0-4：API 版本化（`/api/v1/`）

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P0-04 |
| **优先级** | P0（Must） |
| **用户故事** | US-04 |
| **描述** | 将所有 API 路由前缀从 `/api/` 改为 `/api/v1/`。在 `app.py` 中通过 `prefix` 参数统一注册，或在每个路由文件的 `APIRouter(prefix="/api/v1/...")` 中设置 |
| **涉及模块与文件** | `app.py`（`include_router` 加 `prefix`）；所有 `routes/*.py`（`APIRouter` 内 `prefix` 调整）；`static/index.html`（前端 API 调用路径更新）；`routes/__init__.py`（文档注释更新） |
| **验收标准** | • 所有端点可通过 `/api/v1/` 访问（如 `/api/v1/papers`、`/api/v1/search`）<br>• 旧 `/api/` 路径保持兼容（可返回 301 或保留一份路由别名）<br>• OpenAPI schema（`/docs`）中的路径带 `v1` 前缀 |
| **依赖** | 建议在 P0-02 后做，路由文件稳定后再改 prefix |

#### P0-5：操作审计日志表

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P0-05 |
| **优先级** | P0（Must） |
| **用户故事** | US-05 |
| **描述** | 新增 `audit_log` 表 + 审计日志中间件，记录每次写操作（POST/PUT/DELETE）的请求信息。当前项目中的 `verification_audit` 表是**试卷真实性审核**，非操作审计日志，不可混淆。 |
| **涉及模块与文件** | `models.py`（**新建** `audit_log` 表：`id, user, action, resource_type, resource_id, ip_address, user_agent, detail, created_at`）；`app.py`（**新增**审计中间件）；`config.py`（审计相关配置如是否跳过健康检查路径） |
| **验收标准** | • `audit_log` 表创建成功（版本化迁移 v3）<br>• 每次 POST/PUT/DELETE 请求自动插入一条审计记录<br>• 审计字段完整：user、action、resource_id、ip、timestamp<br>• GET 请求不审计<br>• `pytest` 通过 |
| **依赖** | 无（可独立进行） |

#### P0-6：JWT + RBAC 鉴权体系 + CORS 严格白名单

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P0-06 |
| **优先级** | P0（Must） |
| **用户故事** | US-06, US-07 |
| **描述** | 替换当前 `AuthMiddleware`（单 API Key + CORS 通配符 `*`），引入 JWT 令牌发放/验证 + 基于角色的访问控制（RBAC）+ CORS 严格白名单。包括：用户注册/登录端点、JWT 中间件、角色表、权限装饰器、CORS 来源列表从环境变量读取。 |
| **涉及模块与文件** | `app.py`（替换 `AuthMiddleware`，注册 JWT 中间件；修改 CORS 配置）；**新建** `services/auth_service.py`（JWT 发行/验证、用户 CRUD、角色校验）；**新建** `repositories/user_repo.py`（用户表 DAO）；`models.py`（**新建** `users` 表、`roles` 表、`user_roles` 关联表）；`config.py`（**新增** `JWT_SECRET`、`JWT_ALGORITHM`、`JWT_EXPIRE_MINUTES`、`CORS_ORIGINS_STRICT` 配置）；`deps.py`（**新增** `get_current_user`、`require_role` 等依赖） |
| **验收标准** | • `/api/v1/auth/login` 返回 JWT token<br>• 受保护端点需 `Authorization: Bearer <token>`，无效 token 返回 401<br>• 不同角色（admin/teacher/viewer）对同一资源有不同访问权限<br>• CORS 头中 `Access-Control-Allow-Origin` 严格匹配环境变量 `CORS_ORIGINS` 列表中的值，不再为 `*`<br>• 现有 API Key 可保留为兼容模式（静默降级）<br>• `pytest` 通过 |
| **依赖** | 依赖 P0-05（审计日志）可以复用中间的鉴权用户信息 |

---

### P1 需求（应该做，共 5 项）

#### P1-1：Redis 缓存层

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P1-01 |
| **优先级** | P1（Should） |
| **用户故事** | US-08 |
| **描述** | 引入 Redis 作为分布式缓存，对分析报告、FTS 搜索结果做 TTL 缓存（默认 5 分钟）。进程内 LRU 缓存保留为 L1，Redis 为 L2。通过环境变量开关（无 Redis 时降级为仅 L1）。 |
| **涉及模块与文件** | `config.py`（**新增** `REDIS_URL`、`CACHE_TTL` 配置）；**新建** `services/cache_service.py`（Redis 客户端封装 + get/set/delete + 降级逻辑）；`services/` 中调用（如 `analysis_service`、`search_service` 查询前先查缓存）；`lifespan.py`（**新增** Redis 连接初始化/关闭）；`requirements.txt`（**新增** `redis>=5.0`） |
| **验收标准** | • 相同参数的分析请求第二次返回时间 < 50ms（首次可能 > 1s）<br>• 缓存键含版本号，更新时自动失效<br>• 无 Redis 时自动降级（不报错，走原始计算）<br>• `pytest` 通过 |
| **依赖** | 依赖 P0-02（三层架构）—— 缓存应注入到 services 层，非路由层 |

#### P1-2：Celery + Redis 异步任务

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P1-02 |
| **优先级** | P1（Should） |
| **用户故事** | US-09 |
| **描述** | 将分析（analyze）、模拟（simulate）、采集（collect）三个耗时端点转为 Celery 后台异步任务。提供任务提交端点、任务状态轮询端点、进度获取端点。使用 Redis 作为 broker。 |
| **涉及模块与文件** | **新建** `tasks/` 目录 + `tasks/__init__.py`、`tasks/analysis_tasks.py`、`tasks/simulation_tasks.py`、`tasks/collect_tasks.py`（Celery task 定义）；**新建** `celery_app.py`（Celery 应用实例）；**修改** `routes/papers.py`（analyze/simulate 端点改为提交任务）；`routes/scrape.py`（collect 端点改为提交任务）；**新建** `routes/tasks.py`（**新建**任务状态轮询端点 `/api/v1/tasks/{task_id}`）；`config.py`（**新增** `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`）；`requirements.txt`（**新增** `celery>=5.3`） |
| **验收标准** | • 请求分析/模拟/采集端点返回 202 + `task_id`<br>• 轮询 `/api/v1/tasks/{task_id}` 返回 `pending/running/success/failure` + 进度百分比<br>• 任务完成时结果可获取<br>• Celery worker 可独立启动<br>• `pytest` 通过 |
| **依赖** | 依赖 P0-02（三层架构）+ P1-01（Redis）—— Celery 需要 Redis broker，services 层封装后 task 调用更方便 |

#### P1-3：分析器插件化（BaseAnalyzer 抽象类）

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P1-03 |
| **优先级** | P1（Should） |
| **用户故事** | US-10 |
| **描述** | 将当前 6 维度硬编码的质量分析改为插件体系：定义 `BaseAnalyzer` 抽象基类（含 `analyze(dimensions, weights)` 接口），各维度独立实现并注册到 `AnalyzerRegistry`，支持运行时调整各维度权重。 |
| **涉及模块与文件** | **新建** `analyzers/` 目录 + `analyzers/__init__.py`、`analyzers/base.py`（BaseAnalyzer 抽象类 + AnalyzerRegistry）、`analyzers/difficulty.py`、`analyzers/knowledge_coverage.py`、`analyzers/type_distribution.py`、`analyzers/discrimination.py`、`analyzers/reliability.py`、`analyzers/validity.py`；**修改** `paper_analysis.py`（PaperAnalyzer 改为使用 AnalyzerRegistry 加载插件）；`config.py`（`ANALYSIS_WEIGHTS` 改为实例级的可调配置）；`deps.py`（**新增** 注册表依赖） |
| **验收标准** | • 6 个维度各自为独立类，继承 `BaseAnalyzer`<br>• `AnalyzerRegistry.register()` + `resolve()` 正常工作<br>• 新增自定义分析器无需改框架代码，仅需注册<br>• 权重通过请求参数或配置可调<br>• 向后兼容未注册的分析器<br>• `pytest` 通过 |
| **依赖** | 依赖 P0-02（三层架构）—— 分析器注入到 services 层 |

#### P1-4：i18n 国际化

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P1-04 |
| **优先级** | P1（Should） |
| **用户故事** | US-11 |
| **描述** | 将前端 `static/index.html` 和所有后端返回给前端的文本抽取到 `locales/zh.json` + `en.json` 文件中。前端通过 js 动态加载 locale 文件渲染，后端根据 `Accept-Language` 头返回对应文本。 |
| **涉及模块与文件** | **新建** `locales/zh.json`、`locales/en.json`（键值对语言包）；**新建** `services/i18n_service.py`（后端文本翻译服务）；`static/index.html`（前端 JS 动态加载 locale，替换硬编码中文文本）；`static/i18n.js`（**新建**前端 i18n 工具函数）；`routes/*.py`（所有返回给用户的字符串改为 i18n 调用） |
| **验收标准** | • 前端所有用户可见文本（菜单、标签、提示、错误消息）通过 locale 文件渲染<br>• 支持中英文切换（URL query 参数或浏览器语言检测）<br>• 后端错误消息支持 `Accept-Language` 头<br>• `zh.json` 与 `en.json` 键数量一致<br>• `pytest` 通过 |
| **依赖** | 建议在 P0-02 之后进行（路由稳定后抽取文本不易冲突） |

#### P1-5：Numba JIT 加速

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P1-05 |
| **优先级** | P1（Should） |
| **用户故事** | US-12 |
| **描述** | 对 `simulator.py` 中蒙特卡洛模拟的热点循环（如 `simulate()` 方法中的大量 numpy 向量化操作）加 `@njit` 装饰器加速。当前全仓无 `@njit` 使用。 |
| **涉及模块与文件** | `simulator.py`（**修改**：将关键循环提取为纯 Python/numpy 函数，加 `@njit` 装饰器）；`requirements.txt`（**新增** `numba>=0.59`）；`pyproject.toml`（mypy 配置可能需要忽略 numba 装饰器类型） |
| **验收标准** | • 启用 Numba 后 10 万考生模拟时间缩短 ≥ 3 倍（对比基准为无 JIT 版本）<br>• `@njit` 装饰的函数进入缓存后第二次调用比第一次快<br>• 无 Numba 环境可自动降级（纯 numpy 版本保留）<br>• `pytest` 通过 |
| **依赖** | 无（可独立进行） |

---

### P2 需求（可以做，共 5 项）

#### P2-1：PWA（渐进式 Web 应用）

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P2-01 |
| **优先级** | P2（Nice） |
| **用户故事** | US-13 |
| **描述** | 添加 `manifest.json` + Service Worker + 离线缓存策略，使前端 SPA 可安装到用户桌面/手机桌面，离线时可访问最近浏览的分析报告。 |
| **涉及模块与文件** | **新建** `static/manifest.json`；**新建** `static/sw.js`（Service Worker，缓存策略：Network First for API， Cache First for static assets）；`static/index.html`（添加 manifest link + Service Worker 注册脚本）；`lifespan.py`（可选：启动时生成 manifest 动态字段） |
| **验收标准** | • Lighthouse PWA 审计得分 ≥ 70<br>• 手机浏览器可弹出「添加到主屏幕」提示<br>• 离线时仍可查看已缓存的前端页面和最近报告<br>• Service Worker 注册成功，无报错 |
| **依赖** | 无（可独立进行） |

#### P2-2：多租户数据隔离

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P2-02 |
| **优先级** | P2（Nice） |
| **用户故事** | US-14 |
| **描述** | 在核心业务表（papers、questions、analysis_results 等）中增加 `tenant_id` 字段，通过 JWT 中的 tenant 声明 + 中间件自动注入到所有查询中，实现一套部署服务多校/多机构。 |
| **涉及模块与文件** | `models.py`（所有业务表加 `tenant_id TEXT NOT NULL DEFAULT ''`）；`repositories/*.py`（所有 DAO 方法加 `tenant_id` 参数）；`services/auth_service.py`（JWT payload 含 `tenant_id`）；`app.py`（**新增**租户注入中间件：从当前用户 token 提取 `tenant_id` 注入 request.state）；`deps.py`（**新增** `get_current_tenant` 依赖） |
| **验收标准** | • 不同租户的数据查询结果完全隔离<br>• 超管可跨租户查询<br>• 未指定租户的请求使用默认租户（或拒绝）<br>• 迁移脚本对已有数据填充默认 `tenant_id`<br>• `pytest` 通过 |
| **依赖** | 强依赖 P0-06（JWT+RBAC）和多租户隔离的前提 |

#### P2-3：Docusaurus 文档站

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P2-03 |
| **优先级** | P2（Nice） |
| **用户故事** | US-15 |
| **描述** | 搭建 Docusaurus 2/3 文档站，包含：快速开始（5 分钟部署）、API 参考（集成 OpenAPI）、部署指南（Docker/裸机/云）、FAQ 与常见问题、CHANGELOG。 |
| **涉及模块与文件** | **新建** `website/` 目录（Docusaurus 项目）；`website/docs/`（文档 Markdown）；`website/openapi/`（OpenAPI spec 集成）；`website/sidebars.js`（导航结构）；`website/docusaurus.config.js`（站点配置） |
| **验收标准** | • `yarn build` 成功生成静态站<br>• 包含快速开始、API 参考、部署指南、FAQ 页面<br>• OpenAPI 集成显示所有 `/api/v1/*` 端点<br>• 部署后可独立访问（非嵌入 FastAPI） |
| **依赖** | 建议在 P0-04（API 版本化）之后，API 路径稳定后再集成 OpenAPI |

#### P2-4：Meilisearch 替换 FTS5

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P2-04 |
| **优先级** | P2（Nice） |
| **用户故事** | US-16 |
| **描述** | 引入 Meilisearch 作为全文搜索引擎，替换当前 SQLite FTS5。利用 Meilisearch 的中文分词、容错纠错、搜索结果高亮、分面搜索、排序等能力。FTS5 保留为冷备。 |
| **涉及模块与文件** | `config.py`（**新增** `MEILISEARCH_URL`、`MEILISEARCH_API_KEY`）；`search.py`（SearchEngine 重构：索引时写 FTS5 + Meilisearch，查询优先走 Meilisearch）；`lifespan.py`（启动时索引同步）；`requirements.txt`（**新增** `meilisearch>=0.30`）；`docker-compose.yml`（**新增** Meilisearch 服务） |
| **验收标准** | • 中文搜索分词正确（如「函数导数」能匹配「导数与函数」）<br>• 输入错别字（如「倒數」）能模糊匹配正确结果<br>• 搜索结果带高亮片段<br>• 响应时间 < 200ms（大语料）<br>• Meilisearch 不可用时自动降级到 FTS5<br>• `pytest` 通过 |
| **依赖** | 建议在 P1-01（Redis 缓存）之后，避免同时引入多个新基础设施 |

#### P2-5：社区运营基础

| 字段 | 内容 |
|------|------|
| **ID** | REQ-P2-05 |
| **优先级** | P2（Nice） |
| **用户故事** | US-17 |
| **描述** | 建立开源社区运营基础文件：`CONTRIBUTING.md`（贡献指南）、Issue 模板（bug/feature/question）、PR 模板、`CODE_OF_CONDUCT.md`。配置 SemVer 版本发布流程、GitHub Release、PyPI 包发布流水线、在线 Demo。 |
| **涉及模块与文件** | **新建** `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`；**新建** `.github/ISSUE_TEMPLATE/bug_report.md`、`.github/ISSUE_TEMPLATE/feature_request.md`；**新建** `.github/PULL_REQUEST_TEMPLATE.md`；**新建** `CHANGELOG.md`；**修改** `.github/workflows/ci.yml`（**新增**发布流水线）；**新建** `pyproject.toml`（完善 PyPI 构建配置）；`README.md`（更新徽章和安装方式） |
| **验收标准** | • CONTRIBUTING.md 包含：环境搭建、代码风格、PR 流程<br>• Issue/PR 模板合并后 GitHub 自动识别<br>• `git tag vX.Y.Z` 触发 GitHub Release<br>• PyPI 包 `gaokao-analyzer` 可 `pip install`<br>• 在线 Demo 可通过公共 URL 访问（Vercel/Railway） |
| **依赖** | 建议在 P0 所有项完成后，代码质量有保障后再向社区开放 |

---

## 4. 涉及模块与文件总览

### P0 模块变更矩阵

| 文件 | P0-01 测试 | P0-02 三层架构 | P0-03 mypy | P0-04 版本化 | P0-05 审计日志 | P0-06 JWT+RBAC |
|------|:---------:|:------------:|:---------:|:----------:|:------------:|:-------------:|
| `app.py` | | ✓ | ✓ | ✓ | ✓ | ✓ |
| `config.py` | | | ✓ | | ✓ | ✓ |
| `models.py` | | | ✓ | | ✓ | ✓ |
| `deps.py` | | ✓ | ✓ | | | ✓ |
| `lifespan.py` | | ✓ | ✓ | | | |
| `routes/*.py` (7个) | | ✓ | ✓ | ✓ | | |
| `paper_analysis.py` | ✓ | ✓ | ✓ | | | |
| `scraper.py` | ✓ | | ✓ | | | |
| `search.py` | ✓ | | ✓ | | | |
| `analyzer.py` | ✓ | | ✓ | | | |
| `simulator.py` | ✓ | | ✓ | | | |
| `static/index.html` | | | | ✓ | | |
| `services/` (新建) | | ✓ | | | | ✓ |
| `repositories/` (新建) | | ✓ | | | | ✓ |
| `services/auth_service.py` (新建) | | | | | | ✓ |
| `repositories/user_repo.py` (新建) | | | | | | ✓ |
| `tests/` (扩展/新建) | ✓ | | | | | |

### P1 模块变更矩阵

| 文件 | P1-01 Redis | P1-02 Celery | P1-03 插件化 | P1-04 i18n | P1-05 Numba |
|------|:---------:|:----------:|:----------:|:---------:|:----------:|
| `config.py` | ✓ | ✓ | ✓ | | |
| `lifespan.py` | ✓ | | | | |
| `paper_analysis.py` | | | ✓ | | |
| `simulator.py` | | | | | ✓ |
| `services/cache_service.py` (新建) | ✓ | | | | |
| `tasks/` (新建) | | ✓ | | | |
| `celery_app.py` (新建) | | ✓ | | | |
| `routes/tasks.py` (新建) | | ✓ | | | |
| `analyzers/` (新建) | | | ✓ | | |
| `locales/` (新建) | | | | ✓ | |
| `static/i18n.js` (新建) | | | | ✓ | |
| `routes/*.py` | | ✓ | | ✓ | |
| `requirements.txt` | ✓ | ✓ | | | ✓ |
| `docker-compose.yml` | ✓ | ✓ | | | |

### P2 模块变更矩阵

| 文件 | P2-01 PWA | P2-02 多租户 | P2-03 文档站 | P2-04 Meilisearch | P2-05 社区 |
|------|:--------:|:----------:|:-----------:|:---------------:|:---------:|
| `static/manifest.json` (新建) | ✓ | | | | |
| `static/sw.js` (新建) | ✓ | | | | |
| `models.py` | | ✓ | | | |
| `repositories/*.py` | | ✓ | | | |
| `services/auth_service.py` | | ✓ | | | |
| `app.py` | | ✓ | | | |
| `config.py` | | | | ✓ | |
| `search.py` | | | | ✓ | |
| `lifespan.py` | | | | ✓ | |
| `website/` (新建) | | | ✓ | | |
| `docs/` | | | ✓ | | |
| `CONTRIBUTING.md` (新建) | | | | | ✓ |
| `.github/ISSUE_TEMPLATE/` (新建) | | | | | ✓ |
| `.github/workflows/` (修改) | | | | | ✓ |
| `docker-compose.yml` | | | | ✓ | |

---

## 5. 依赖与执行顺序

### 推荐执行顺序图

```
P0-01 测试覆盖率  ──→  并行可做
        │
P0-03 mypy ──────────→ 可在 P0-02 前后
        │
P0-02 三层架构 ───────────────┬──────────────────┬──────────────┐
        │                     │                  │              │
        ▼                     ▼                  ▼              ▼
P0-04 API 版本化       P1-01 Redis 缓存    P1-03 插件化    P1-04 i18n
        │                     │                  │              │
P0-05 审计日志               ▼                  │              │
        │              P1-02 Celery 异步  ←──────┘              │
        ▼                                                       │
P0-06 JWT+RBAC ─────────┬───────────────────────────────────────┘
        │                │
        ▼                ▼
P2-02 多租户         P2-03 文档站
                        │
P1-05 Numba JIT  ──→  独立可并行

P2-01 PWA      ──→  独立可并行
P2-04 Meilisearch ─→  建议在 P1-01 之后
P2-05 社区运营   ──→  建议 P0 全部完成之后
```

### 前置条件说明

| 需求 | 前置条件 | 原因 |
|------|---------|------|
| P1-01 Redis 缓存 | P0-02 三层架构 | 缓存逻辑应注入到 services 层，非路由层 |
| P1-02 Celery 异步 | P0-02 + P1-01 | Celery 依赖 Redis broker；任务调用 services 层 |
| P1-03 插件化 | P0-02 三层架构 | 插件应在 services 层注册和调用 |
| P1-04 i18n | P0-02（建议） | 路由稳定后再抽取文本不易冲突 |
| P2-02 多租户 | P0-06 JWT+RBAC | 租户信息从 JWT token 提取 |
| P2-03 文档站 | P0-04 API 版本化 | API 路径稳定后再集成 OpenAPI |
| P2-04 Meilisearch | P1-01（建议） | 避免同时引入多个新基础设施 |
| P2-05 社区运营 | 全部 P0 | 代码质量有保障后再向社区开放 |

---

## 6. 验收标准汇总

### P0 整体验收

| 验收项 | 达标标准 |
|--------|---------|
| 测试覆盖率 | `pytest --cov-report=term-missing` 行覆盖率 ≥ 50%，总测试函数 ≥ 40 |
| 三层架构 | `routes/*.py` 中零裸 SQL，所有 DB 操作经 repositories，所有业务编排经 services |
| mypy strict | `mypy src/`（不含 tests）零错误 |
| API 版本化 | 全量端点前缀 `/api/v1/`；旧路径兼容或重定向 |
| 审计日志 | 每次写操作自动记录 `audit_log`；字段完整 |
| JWT+RBAC | 登录返回 token；角色隔离有效；CORS 来源白名单；无 `*` |
| 全部 | `pytest` 100% 通过，CI 门禁绿 |

### P1 整体验收

| 验收项 | 达标标准 |
|--------|---------|
| Redis 缓存 | 相同请求二次响应 < 50ms；无 Redis 降级正常 |
| Celery 异步 | 3 个耗时端点返回 202 + task_id；轮询进度；worker 独立运行 |
| 插件化 | 6 维度独立类注册；新增维度无需改框架；权重可调 |
| i18n | 中英切换；前后端文本全量抽取；键数量一致 |
| Numba JIT | 10 万考生模拟时间缩短 ≥ 3 倍；无 numba 降级正常 |

### P2 整体验收

| 验收项 | 达标标准 |
|--------|---------|
| PWA | Lighthouse PWA ≥ 70；可安装；离线可看 |
| 多租户 | `tenant_id` 隔离；超管可跨租户；迁移脚本 |
| 文档站 | Docusaurus build 成功；4 个页面；OpenAPI 集成 |
| Meilisearch | 中文分词+纠错+高亮；响应 < 200ms；降级正常 |
| 社区运营 | 模板就位；SemVer 发布；PyPI 包；在线 Demo |

---

## 7. 待确认问题

1. **测试覆盖率目标**：50% 行覆盖率是否包括前端？当前仅后端 Python 代码。前端 `static/index.html` 目前无测试，50% 目标是否仅限后端？
2. **三层架构边界**：路由层是否允许调用 `Depends(get_db)` 直连？还是所有 DB 操作必须通过 repositories？健康检查等简单查询是否可以例外？
3. **JWT 密钥管理**：P0-06 的 JWT_SECRET 是否走环境变量？还是引入 Vault/密钥管理服务？
4. **Celery broker 选择**：P1-02 是否固定为 Redis？还是保留 `CELERY_BROKER_URL` 配置灵活性（如支持 RabbitMQ）？
5. **Meilisearch 部署方式**：P2-04 的 Meilisearch 是否内嵌到 `docker-compose.yml`？还是要求用户自行部署？
6. **i18n 范围**：P1-04 的前端 i18n 是否覆盖所有 Chart.js 图表的标签和 tooltip？后端错误消息是否全部需要 i18n 化？
7. **Numba 降级策略**：P1-05 的无 Numba 降级是运行时检测 import 失败还是通过配置开关？是否需要在 `pyproject.toml` 中声明可选依赖？
8. **多租户零迁移**：P2-02 的 `tenant_id` 迁移对已有数据是否必须？能否仅新数据默认 `tenant_id='default'`？
9. **工作量估算不确定性**：P0-02 三层架构估算 2-3 天，如果 `routes/papers.py`（800+ 行裸 SQL 动作最多）抽取工作量大，是否可分批进行（先抽一个路由验证模式）？
10. **P0/P1/P2 的边界弹性**：若时间紧张，P1-05（Numba JIT 仅 0.5 天）是否可提前到 P0 末期做？同理 P0-03（mypy strict）若 1 天不够是否可放宽到仅 P0-06 涉及的代码？

---

## 8. 附录：当前工程基线已落地项

以下项已在 v5.1（2026-07-07）完成，不在本 PRD 范围内：

- ✅ Docker 化（`Dockerfile` + `docker-compose.yml`）
- ✅ `.pre-commit-config.yaml`（ruff/black/mypy/pytest）
- ✅ CI 流水线（`.github/workflows/ci.yml`）
- ✅ 安全头（HSTS / X-Content-Type-Options / X-Frame-Options / Referrer-Policy）
- ✅ slowapi 全局限速（200/min，优雅降级）
- ✅ 运行时上下文集中化（`app_context.py` + `app.state.ctx`）
- ✅ 异常处理器（通用+HTTP 分离，不泄漏内部路径）
- ✅ 引擎初始化并行化（`asyncio.gather`）
- ✅ 依赖注入体系（`deps.py` + `app.state.*`）
- ✅ 爬虫可插拔（`AdapterRegistry` + `SCRAPER_ADAPTER_TYPES`）
