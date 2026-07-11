# gaokao-analyzer 产品路线图

## v6.1（短期，2026 Q3）
- [x] CI 强化：mypy 全量阻塞 + pip-audit + 前端 build 纳入 CI（pip-audit 作非阻塞警告）
- [x] OR-Tools 组卷引擎：CP-SAT 约束求解已实现并接入 composition_service（`engines/composition_engine.py`）
- [x] PostgreSQL 正式切：完成 SQLite→PG 生产迁移（docker-compose.prod + `.env.example` + `scripts/migrate_to_pg.py`）
- [~] 试卷数据采集：合成种子已完成（`scripts/seed_synthetic_data.py`，默认 1000 模拟卷 + 近 5 年真题风格卷，共 ~1090 套 / 2 万+ 题入库）；**真实卷待学科网/组卷网凭据或本地导出文件后导入**（见下）
- [x] 一键部署体验优化：Docker Compose 一键启动生产环境（`docker-compose.prod.yml` + `Docker一键启动.bat` 已 `chcp 65001` 解决编码）

### 真实卷子导入通道（数据采集 v6.1 剩余项）
学科网 / 组卷网需付费登录，无法直接爬取真实版权卷。提供两条导入路径：
1. **账号凭据接入**：在 `edu_source_adapters.py` 新增/启用对应适配器，填入账号后由 `auto_scraper.py` / `scrape_service` 采集入库。
2. **本地导出文件导入**：将学科网/组卷网导出的 txt / 图片 / Excel 放到 `data/downloads/`，新增解析脚本写入 `papers` / `questions`（schema 与 `scripts/seed_synthetic_data.py` 一致，建议 `source_id` 设为真实来源、`collector` 非空以便追溯）。
> 合成数据均带 `collector='seed-script'` 与 `content_hash`，与既有 `dedup_records` 去重流程兼容，真实卷入库后可通过 `dedup_status` 区分。

## v6.2（中期，2026 Q4）
- [ ] 移动端适配：PWA 增强（Service Worker + 离线缓存）
- [ ] 组卷导出增强：Word（python-docx）+ LaTeX 模板
- [ ] 班级/学校级多租户：行级数据隔离 + 管理后台
- [ ] 学情报告自动生成：定时推送学生/教师周报

## v7.0（长期，2027）
- [ ] 原生移动 App（iOS/Android）：Flutter 或 React Native
- [ ] AI 辅助组卷：大模型自然语言指令（DeepSeek 集成）
- [ ] 拍照搜题/OCR 识别：自动录入纸质试卷
- [ ] 企业版：私有部署 + 技术支持 + 定制开发
- [ ] 开放平台：API 市场 + 第三方插件生态
