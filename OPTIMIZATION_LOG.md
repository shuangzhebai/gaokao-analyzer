# gaokao-analyzer 优化执行日志（自主运行）

> 执行时间：2026-07-07（本地时区 GMT+8）
> 执行者：主理人齐活林（交付总监）+ 工程师（寇豆码）+ 主理人验证
> 项目路径：`C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer`
> 操作范围：仅限本项目目录，未触碰项目外任何文件/配置/系统设置。

## 阶段交付清单（已提交）

| 阶段 | Commit | 内容 |
|------|--------|------|
| 阶段一 T01–T05 | `826fa53` | 版本化 DB 迁移（防删库）、搜索相关度修复、app.py 拆分(1258→67 行)、异常安全、请求级连接池 |
| 阶段二 后端 | `7a69c31` | 爬虫重写（弃用 DeepSeek，可插拔数据源适配器 + 反爬 + 去重）、6 维度分析、批量并行、报告 API、测试 9/9 |
| 阶段三 前端 | `dbd9a82` | 液态玻璃动效（毛玻璃质感 + 弹性过渡 + 骨架屏/空态/错态 + 尊重 reduced-motion）、分析报告可视化（雷达/柱状/难度曲线四图） |

## 验证记录

| 任务 | 时间 | 结果 | 说明 |
|------|------|------|------|
| 后端 pytest 回归 | - | PASS | 9 passed（分析维度+批量并行+爬虫适配器） |
| 前端 JS 语法检查 | - | PASS | `node --check` 通过（875 行内联 JS） |
| 端到端分析冒烟（英文科目） | - | PASS | 6 维齐全、综合分/等级/结论/可视化数组均符合前端契约；8 题 ~16ms |
| OpenAPI 路由挂载复核 | - | PASS | 39 条路径，含 `/api/papers/{id}/analyze`、`/analyze/batch`、`/report` |

## 缺陷发现与修复

### Bug A（准确度缺陷，已修复）
- **现象**：真实试卷（科目为中文"数学"）分析时 `knowledge_coverage` 与 `validity` 恒为 0。
- **根因**：`KNOWLEDGE_SEED` / `get_question_type_preset` / `KnowledgeMapper` 均以英文 key（"math"）查表，而 `_paper_subject` 返回中文科目名，导致查空池。测试样例用了英文 "math" 掩盖了该问题。
- **修复**：`config.py` 新增 `SUBJECT_NAME_TO_KEY` 与 `normalize_subject()`；在 `paper_analysis.py` 的 KNOWLEDGE_SEED 查找、题型预设、知识点映射处统一归一为英文 key。
- **修复后**：中文科目卷 `knowledge_coverage=52.63`、`validity=21.05`，恢复正常。

### Bug B（探针误报，已澄清）
- **现象**：初次路由检查显示分析路由 MISSING。
- **结论**：误报。`include_router` 正常，Starlette 将 include 的路由包为 `_IncludedRouter`（path=None），真实路径经 OpenAPI 复核共 39 条，全部挂载。

## 已知限制
- 沙箱网络受限，爬虫仅验证了「本地 fixture 适配器」与「通用网页适配器（BS4 + 可配置选择器）」框架正确性；真实外部站点端到端爬取未在沙箱内实测，接入只需在 `config.DATA_SOURCES` 增一条数据源配置。
- 前端液态玻璃视觉/动效未做浏览器实跑（按任务要求未启动服务器），建议本地 `python -m http.server` 预览确认。

## 下一步（留给用户）
1. 本地预览：`python start.py` 或 `python -m http.server 8000` → 打开 `/static/index.html`，点开试卷 →「质量分析报告」。
2. 推送 GitHub：需提供有 `repo` 写权限的 Personal Access Token（见推送步骤）。
