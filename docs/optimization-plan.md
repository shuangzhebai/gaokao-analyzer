# 高考模拟卷智能分析系统（gaokao-analyzer v5.1）代码评估与优化方案

> 评估人：架构师（高见远）　|　评估对象：`C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer`
> 说明：本报告仅做代码评估与方案设计，未修改任何源码。

---

## 一、现状评估摘要

### 1.1 架构概览

系统是一个 **FastAPI 单体应用**（无分层/蓝图拆分），后端按"模块文件"组织，前端为单文件 `static/index.html`（原生 HTML/CSS/JS + Chart.js）。核心数据链路：

```
采集(scraper/auto_scraper) → 入库(papers/questions, FTS5 同步) → 分析(analyzer/simulator/quality/curriculum) → 校验(auth_verifier/region_validator/dedup) → 前端展示
```

- **Web 层**：`app.py`（~1258 行，47KB）承载全部路由、异常处理、启动逻辑、业务逻辑。
- **数据层**：`models.py`（aiosqlite + FTS5 外部内容表 + 触发器同步）。
- **算法层**：`analyzer.py`（IRT 3PL 估计）、`simulator.py`（蒙特卡洛 + 偏态校准）、`quality.py`、`curriculum.py`。
- **采集层**：`scraper.py`、`auto_scraper.py`（含 `CrossVerifier`）。
- **支撑层**：`config.py`、`search.py`（FTS5 + 自研中文分词）、`dedup.py`（三级查重）、`region_validator.py`、`auth_verifier.py`、`official_docs.py`、`parser.py`、`sample_data.py`。

### 1.2 规模统计（近似）

| 维度 | 数值 |
|------|------|
| Python 源码文件 | 17 个（不含测试/辅助脚本） |
| Python 代码行数 | 约 6,700 行 |
| 最大文件 | `app.py` ~1258 行 |
| 单测覆盖 | 仅 `verify_v5.py` / `test_quick.py` 导入冒烟测试，无业务逻辑单测 |
| 默认种子数据 | 1000 份试卷（800 模拟 + 200 真题），每卷约 8–18 题 |
| 默认模拟考生数 | `MC_CONFIG.n_students=100000`；种子生成用 5000 |
| 前端 | 单文件 `index.html` 约 56KB，无构建工具 |

### 1.3 主要问题（Top 10，按影响排序）

1. **`app.py` 单文件过大**（~1258 行），路由、异常、启动、业务逻辑全耦合，可维护性与可测试性差。
2. **数据库迁移即清空数据**：`app.py:104-106`、`start.py:53-54` 在 schema 不兼容时直接 `os.remove(db_path)`，无法平滑升级（已知限制 #4）。
3. **中文搜索相关性排序失效**：`search.py:217-218` 用 `CASE ... THEN 0 ELSE 1` 实现，匹配结果实际按 `created_at` 排序，**FTS 相关度被忽略**。
4. **采集落库但未下载文件**：`app.py:997-1027` 计算了 `file_path` 却从未调用 `scraper.download(...)`，落库的 `file_path` 指向不存在的文件（死引用）。
5. **种子生成 IRT 估计性能瓶颈**：`sample_data.py` + `analyzer.estimate_parameters` 对 ~15000 道题逐题跑 `scipy.optimize.minimize`（L-BFGS-B），单次建库 1–3 分钟且不可并行。
6. **自动采集后台负载重**：`auto_scraper` 默认每 30 分钟对 7 个外部源 × 9 科 × 2 年轮询（每次 2s 延迟），`CrossVerifier` 再叠加一次，易被封且长期占用 IO。
7. **`get_db()` 每次请求新建/关闭连接**，无连接池，并发下资源浪费。
8. **三级查重 FTS 路径弱于搜索路径**：`dedup._fts_check` 仅做单次短语 FTS，无 AND/OR 降级（而 `search.py` 有），一致性差。
9. **全局异常向客户端泄露原始错误**：`app.py:43-49` 直接返回 `str(exc)`，存在信息泄露与体验问题。
10. **配置在导入期一次性读取环境变量**：`config.py:364-365` 的 `DEEPSEEK_API_KEY` 在 import 时固定，运行时变更不生效；`start.py:107` 每次启动都 `pip install`。

> 其余问题按维度见第二章。

---

## 二、优化点清单（按维度分组）

> 定位格式：`文件:行号/函数`。影响与建议均给出可落地改法。

### 2.1 性能瓶颈

| # | 问题定位 | 影响 | 建议改法 |
|---|----------|------|----------|
| P-1 | `sample_data.py:492` + `analyzer.py:51-89` `estimate_parameters` 逐题 L-BFGS-B | 建库 ~15000 次 scipy 优化，1–3 分钟且 CPU 密集 | ① 用向量化 Newton-Raphson / MMLE 批量估计；② `estimate_all_questions` 用 `concurrent.futures.ProcessPoolExecutor` 并行题目估计；③ 将 IRT 估计结果缓存，重复生成时跳过 |
| P-2 | `app.py:744-789` `estimate_irt` 与 `608-678` `batch_estimate_irt` 同样逐题优化 | 批量接口（50 卷）可能 30–60s 阻塞单请求 | 抽公共 `estimate_paper_irt(questions)`；批量任务改后台任务 + 进度，避免同步阻塞 |
| P-3 | `simulator.py:160-200` 默认 `n_students=100000` 且 `simulate_comparison` 调用 `simulate` 两次 | 单次比较=20 万考生矩阵运算，CPU 高 | `n_students` 改为可配置（如 2 万足够）；`simulate_comparison` 复用语料/能力分布 |
| P-4 | `simulator.py:381-405` `_compute_test_information` Python 双层 for 循环（41×n_q） | 题目多时偏慢（目前可接受，属隐患） | 向量化为 `(41, n_q)` 矩阵运算 |
| P-5 | `app.py:650-661` `estimate_irt` 用 Python for 循环逐列填 `response_matrix` | 列多时慢 | 按题型一次性 `rng.binomial` 生成整列，去掉列循环 |
| P-6 | `auto_scraper.py:228-259` 每 30 分钟全量轮询 7 源×9 科×2 年 | 后台长时 IO + 被目标站封禁风险 | 改为可配置开关 + 限频 + 增量（仅查新增关键词）；默认关闭或降低频率 |
| P-7 | `app.py:967-1048` `collect_papers` 在 `async for db in get_db()` 内执行 `scraper_manager.collect_all`（含网络） | 网络期间长期占用 DB 连接 | 先完成采集再开 DB 连接写库；或将采集与落库解耦 |

### 2.2 代码质量

| # | 问题定位 | 影响 | 建议改法 |
|---|----------|------|----------|
| Q-1 | `app.py` 整体（~1258 行） | 路由/异常/启动/业务耦合，难测试 | 拆分为 `app.py`（装配）+ `routes/*.py`（按域：papers/search/dedup/scrape/audit/official_docs）+ `errors.py` + `lifespan.py`（用 `@asynccontextmanager` 替代弃用 `@on_event`） |
| Q-2 | `app.py:62-75` 大量模块级全局单例 | 难以注入/测试 | 用依赖注入（`Depends`）获取引擎实例，或在 lifespan 中初始化并存入 `app.state` |
| Q-3 | `search.py:48` 与 `search.py:55` `exam_patterns` 中 `"期末"` 重复 | 冗余、可读性差 | 去重，抽成模块常量 |
| Q-4 | `auto_scraper.py:418`、`official_docs.py:218` 函数内 `from urllib.parse import urljoin` | 重复导入 | 提到文件顶部 |
| Q-5 | `curriculum.py:145` 函数内 `from models import KNOWLEDGE_SEED` | 循环依赖风险（models 不依赖 curriculum，目前安全但脆弱） | 顶部统一导入或传入参数 |
| Q-6 | `simulator.py:585-589` `_calibrate_scores` 仅为 `_calibrate_scores_v2` 的别名 | 死代码/兼容残留 | 保留或明确标注弃用，逐步移除旧引用 |
| Q-7 | `models.py:136` `questions.similar_to`、`papers.duplicate_of` 等字段基本未使用 | 死字段 | 评估后清理或补充用途 |
| Q-8 | 版本标识混乱：`app.py:37/159` 标 `5.0.0`；`search.py`/`simulator.py` docstring `v5.1`；`README` `v5.1`；`overview.md` `v4.0` | 维护者无法确认真实版本 | 统一为单一版本常量（如 `config.VERSION`） |
| Q-9 | `static/index.html` 单文件 56KB | 已知限制 #3，加载慢、难维护 | 引入 Vite 拆分 CSS/JS/组件；或至少把 JS/CSS 抽到独立文件并加缓存指纹 |

### 2.3 健壮性 / 可靠性

| # | 问题定位 | 影响 | 建议改法 |
|---|----------|------|----------|
| R-1 | `app.py:104-106`、`start.py:53-54` schema 不兼容即删库 | 数据清空（已知限制 #4） | 引入 **Alembic/自研版本化迁移**：保留数据，按 `schema_version` 表增量 ALTER；迁移失败才提示重建 |
| R-2 | `app.py:43-49` 全局异常返回 `str(exc)` | 泄露内部细节（路径/SQL），不利安全 | 仅返回 `{"detail":"服务器内部错误"}`，详细日志留服务端 |
| R-3 | `models.py:16-39` `get_db()` 每请求新建连接 | 并发下连接数膨胀 | 用 `aiosqlite` 连接池或请求级单连接复用（FastAPI `Depends` 内开启、响应后关闭） |
| R-4 | `config.py:364-365` `DEEPSEEK_API_KEY` 导入期读取 | 运行时设环境变量不生效 | 改为 `get_deepseek_key()` 惰性读取，或引入 `pydantic-settings` |
| R-5 | `start.py:107` 每次启动 `pip install -q -r requirements.txt` | 启动慢、离线环境失败 | 首次/显式时安装；或改用 `--no-deps` 校验；容器化时构建期装依赖 |
| R-6 | `app.py:1071` `trigger_auto_scrape` 用 `asyncio.create_task` 火忘 | 任务异常无反馈 | 用 `BackgroundTasks` 或记录 task 引用并处理异常 |
| R-7 | `scraper.py:44-52` `fetch` 静默吞异常返回 None | 采集失败难排查 | 记录失败 URL/异常到 `scrape_logs`，区分"无结果"与"出错" |
| R-8 | `dedup.py` / `search.py` 对 FTS 异常统一降级 LIKE | 降级后无提示 | 记录降级原因，便于评估中文分词效果 |

### 2.4 功能正确性（潜在 Bug）

| # | 问题定位 | 影响 | 建议改法 |
|---|----------|------|----------|
| B-1 | `search.py:217-218` 相关性排序 `CASE ... THEN 0 ELSE 1, created_at DESC` | 匹配结果按时间排序，**FTS 相关度被忽略**（"相关度"实际=时间） | 改为 `ORDER BY CASE p.id WHEN <id1> THEN 1 WHEN <id2> THEN 2 ... END`，保留 FTS 排序 |
| B-2 | `app.py:997-1027` `collect_papers` 计算 `file_path` 但未下载 | 落库 `file_path` 指向不存在文件 | 调用 `scraper_manager.download(url, file_path)`，或改为 `None` 并从 UI 隐藏下载入口 |
| B-3 | `dedup.py:119-174` `_fts_check` 仅单次短语 FTS，无 AND/OR 降级 | 查重对多词标题召回率低、与搜索不一致 | 复用 `search.py` 同样的 AND→OR 降级策略 |
| B-4 | `app.py:174` `index()` 同步 `open()` 读 HTML | 阻塞事件循环 | 改 `FileResponse(static/index.html)` 或启动时读入内存缓存 |
| B-5 | `sample_data.py:434` `n_virtual=5000` 与 `MC_CONFIG.n_students=100000` 不一致 | 种子 IRT 参数基于 5000 虚拟考生，与线上 10 万模拟校准口径不一致 | 统一口径或文档说明差异 |
| B-6 | `simulator.py:321` `is_selective = max_score <= 110` 判定选考赋分 | 语文/数学 150 分制不赋分 OK，但 100 分制的"非选考"（如部分省份卷）会被误赋分 | 增加 `subject_id`/卷别显式开关，而非仅按分值 |
| B-7 | `verify_v5.py` / `test_quick.py` 仅导入冒烟 | 算法回归无保障 | 补 IRT/模拟/查重/分词单测（见任务 T08） |

### 2.5 中文搜索体验（重点维度）

现状：`papers_fts`/`questions_fts` 使用 FTS5 默认 `unicode61` 分词器，对中文按**单字**切分（已知限制 #2）。当前靠 `search.py:_tokenize_chinese` 自研"已知词表 + 2-gram 兜底 + AND/OR 降级 + LIKE 兜底"曲线救国，能覆盖常用词，但：

- 未知新词（如新出现的联考名、学校名）无法命中，退化为 LIKE 全表扫描；
- `dedup._fts_check` 未做 AND/OR 降级，召回更弱（见 B-3）；
- 相关度排序 bug（B-1）进一步削弱体验。

**改进方案（三选一，建议分档落地）：**

| 方案 | 依赖 | 效果 | 复杂度 | 推荐度 |
|------|------|------|--------|--------|
| A. 保留 `unicode61` + 统一分词器 + AND/OR 降级 + 修 B-1 | 无 | 中等（覆盖常见词，未知词降级 LIKE） | 低 | **P1 快速见效** |
| B. 改 FTS5 `trigram` 分词器（SQLite≥3.34 内置） | 无（零依赖） | 子串匹配好；但**中文 2 字词（数学/物理）需≥3 字才命中**，需配合补 3-gram/兜底 | 中 | **P1/P2 推荐（无新依赖）** |
| C. `jieba` 中文分词 + 自定义 FTS5 Python tokenizer | `jieba` | 词级分词最准，最贴近真实搜索 | 中高（需注册 `fts5.tokenizer`） | **P2 长期最优** |

> 结论：先做 **A**（零成本、立刻改善），再评估是否上 **B**（零依赖、子串更强）或 **C**（最准、加依赖）。`requirements.txt` 增加 `jieba` 为可选。

---

## 三、优先级任务列表（P0/P1/P2）

> 粒度适合工程师批量实现；依赖与建议顺序已标注。T 开头为工程实现任务，O 开头为优化专项。

| 任务ID | 任务名称 | 涉及文件（主要） | 依赖 | 优先级 | 说明 |
|--------|----------|------------------|------|--------|------|
| T01 | 修复数据清空：引入版本化 DB 迁移 | `models.py`、`start.py`、`app.py:83-106` | — | **P0** | 用 `schema_migrations` 表 + 增量 ALTER，避免删库；保留数据 |
| T02 | 修复搜索相关度排序 + 统一中文分词/查重降级 | `search.py`、`dedup.py` | — | **P0** | 修 B-1；`dedup` 复用 `search` 的 AND/OR 降级；抽公共分词器 |
| T03 | `app.py` 拆分与lifespan改造 | `app.py` → `routes/*.py`、`errors.py`、`lifespan.py` | — | **P1** | 解耦路由/异常/启动；用 `@asynccontextmanager` 替代 `@on_event` |
| T04 | 异常安全化 + 依赖注入引擎实例 | `app.py`、`errors.py`、`config.py` | T03 | **P1** | 全局异常不泄露；`DeepSeek` 键惰性读取；引擎实例注入 |
| T05 | 连接池化 + 采集落库修复 + 后台任务规范化 | `models.py(get_db)`、`app.py(collect_papers)`、`auto_scraper.py` | T03 | **P1** | 连接复用；`collect_papers` 真正下载或置空 `file_path`；`auto_scraper` 默认关闭/限频 |
| T06 | IRT/模拟性能优化 | `analyzer.py`、`sample_data.py`、`simulator.py`、`app.py(batch_estimate_irt)` | — | **P1** | 批量/并行 IRT 估计；`n_students` 可配；向量化信息量计算 |
| T07 | 中文搜索分词升级（trigram 或 jieba） | `models.py`(FTS 定义)、`search.py`、`dedup.py` | T02 | **P2** | 在 A 方案基础上评估 B/C；如需 jieba 一并改 `requirements.txt` |
| T08 | 单元测试与回归基线 | `tests/`(新建)、`verify_v5.py` | T02,T06 | **P2** | 覆盖 IRT/模拟/查重/分词；CI 可跑 |
| T09 | 前端工程化（构建工具/拆分） | `static/index.html` → `src/` + Vite | — | **P2** | 拆分 CSS/JS，加缓存指纹；可选 |

### 任务依赖关系图（Mermaid）

```mermaid
graph TD
    T01[TP0: 版本化DB迁移-防清空]
    T02[TP0: 搜索相关度+分词/查重降级]
    T03[TP1: app.py拆分+lifespan]
    T04[TP1: 异常安全+依赖注入]
    T05[TP1: 连接池+落库修复+后台规范]
    T06[TP1: IRT/模拟性能]
    T07[TP2: 中文分词升级]
    T08[TP2: 单测基线]
    T09[TP2: 前端工程化]

    T03 --> T04
    T03 --> T05
    T02 --> T07
    T04 --> T05
    T02 --> T08
    T06 --> T08
    T01 -.并行. T02
    T01 -.并行. T03
    T03 -.并行. T06
    T09 -.独立. T09
```

**建议实现顺序**：`T01 → T02`（先止血：数据清空、搜索失效）→ `T03 → T04/T05`（结构解耦与健壮性）→ `T06`（性能）→ `T07/T08`（搜索升级与测试）→ `T09`（前端，可最后或并行）。

---

## 四、依赖包变更建议

| 包 | 变更 | 用途 | 优先级 |
|----|------|------|--------|
| `jieba` | 新增（可选） | 中文词级分词，配合 FTS5 自定义 tokenizer（方案 C） | P2（若选方案 C） |
| `alembic` | 新增（可选） | 数据库版本化迁移（T01 若走标准方案） | P0/P1（替代自研迁移也可） |
| `pydantic-settings` | 新增（可选） | 配置统一管理、惰性读环境变量（R-4） | P1 |
| `pytest` + `pytest-asyncio` | 新增 | 单元测试与回归（T08） | P2 |
| `httpx` | 已存在 | 采集/DeepSeek（无需变更） | — |
| `aiosqlite` | 已存在 | 可配合自建连接池（R-3），无需换库 | — |
| `vite` + `@tailwindcss` 等 | 前端构建（可选） | 前端工程化（T09） | P2 |

> 零依赖路线（推荐先走）：T01 自研迁移表、T07 选 `trigram` 方案——**全程不新增第三方依赖**，降低交付风险。

---

## 五、待明确事项（请主理人向用户确认范围）

1. **优化目标优先级**：用户更看重 (a) 数据不丢失/稳健性、(b) 搜索与中文体验、(c) 性能与并发、(d) 代码可维护性？决定 P0/P1 取舍。
2. **数据库迁移策略**：是否接受"自研轻量迁移表"（零依赖、快），还是要求标准 `Alembic`？是否需要保留历史数据（影响是否允许 ALTER 方案）？
3. **自动采集（auto_scraper）定位**：是核心功能（需保留并优化限频），还是"演示性"功能（默认关闭、改为手动触发）？当前默认开启且高负载。
4. **中文分词方案选择**：A（修复零依赖）/ B（trigram 零依赖）/ C（jieba 加依赖）三选一？是否允许新增 `jieba` 依赖？
5. **DeepSeek 查重**：用户是否会提供 `DEEPSEEK_API_KEY`？若长期不提供，是否弱化三级查重为两级并将配置改为运行时可读（R-4）？
6. **前端改造意愿**：是否同意引入构建工具（Vite）进行前端工程化（T09），还是保持单文件 HTML 仅做最小拆分？
7. **测试与交付门槛**：是否需要补单元测试（T08）作为验收门槛？是否需要 CI？
8. **版本号与 branding**：统一为 `v5.1` 还是另立 `v5.2`？影响改动归属与文档。

---

## 附录：关键文件行号速查（便于工程师落地）

- 全局异常泄露：`app.py:43-49`
- 删库逻辑：`app.py:104-106`、`start.py:53-54`
- 同步读 HTML：`app.py:174`
- 相关性排序 bug：`search.py:217-218`
- 查重 FTS 无降级：`dedup.py:119-174`
- 采集未下载：`app.py:997-1027`
- IRT 逐题优化：`analyzer.py:51-89`、`sample_data.py:492`
- 连接无池：`models.py:16-39`
- 自动采集默认开启：`auto_scraper.py:228-236` + `config.AUTO_SCRAPER_CONFIG.enabled=True`
- 环境变量导入期读取：`config.py:364-365`
- 每次启动 pip：`start.py:107`
