# gaokao-analyzer 产品路线图

## v6.1（短期，2026 Q3）
- [ ] CI 强化：mypy 全量阻塞 + pip-audit + 前端 build 纳入 CI
- [ ] OR-Tools 组卷引擎：安装 ortools 包激活 CP-SAT 约束求解
- [ ] PostgreSQL 正式切：完成 SQLite→PG 生产迁移
- [ ] 试卷数据采集：推进 1000 份模拟卷 + 5 年真题入库
- [ ] 一键部署体验优化：Docker Compose 一键启动生产环境

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
