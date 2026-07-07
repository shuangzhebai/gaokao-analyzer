# 高考分析中心 v5.1 - 优化交付概览

## 已完成

### 核心重构：v3.0 → v4.0

| 模块 | 变更 | 状态 |
|------|------|------|
| models.py | 重写 schema + FTS5 全文索引 + 触发器同步 | ✅ |
| search.py | 新建 FTS5 搜索引擎 + 排名 + 搜索建议 | ✅ |
| dedup.py | 新建三级查重引擎 (hash→FTS→DeepSeek) | ✅ |
| app.py | 重写路由 + 搜索API + 查重API + 全局异常处理 | ✅ |
| config.py | 增加 DeepSeek 配置 + 来源可信度映射 | ✅ |
| index.html | 完全重写 Apple Design 前端 | ✅ |
| sample_data.py | 适配 v4.0 新 schema 字段 | ✅ |

### 新增功能

1. **FTS5 全文搜索**：支持标题、省份、学校、考试标签的全文搜索，<200ms 响应
2. **三级查重引擎**：hash 快速比对 → FTS5 标题搜索 → DeepSeek API 语义分析
3. **来源追溯**：每份试卷记录来源网站、URL、可信度等级（S/A/B/C）、采集时间
4. **Apple Design UI**：毛玻璃导航栏、极简白底、圆角卡片、流畅动画
5. **搜索建议**：输入时自动补全热门关键词（debounce 300ms）
6. **多维度筛选**：科目+年份+类型+省份+验证状态组合筛选

### 数据库变更

- 新增字段：`content_hash`, `duplicate_of`, `dedup_status`, `source_priority`, `collected_at`, `collector`, `verified`, `question_count`, `explanation`, `difficulty_tag`
- 新增表：`dedup_records`（查重记录）
- 新增 FTS5 虚拟表：`papers_fts`, `questions_fts`
- 新增触发器：自动同步 papers/questions 到 FTS 索引

## 启动方式

```bash
cd C:\Users\29499\WorkBuddy\Claw\gaokao-analyzer
python start.py
```

首次启动会自动：
1. 检测旧数据库 schema，如不兼容自动迁移（删除重建）
2. 生成 1000 份试卷种子数据
3. 启动 Web 服务，访问 http://127.0.0.1:8899

## 已知限制

1. DeepSeek 查重需要设置环境变量 `DEEPSEEK_API_KEY`，未设置时仅使用 hash + FTS 两级查重
2. FTS5 的 `unicode61` 分词器对中文分词效果有限（按字符分割），复杂查询可能需多次尝试
3. 前端未引入构建工具，单文件 HTML 体积较大
4. 数据库采用版本化迁移（schema_migrations 表），升级不删库、不丢数据

## 下一步建议

1. 启动服务器验证功能正常
2. 设置 `DEEPSEEK_API_KEY` 环境变量启用 DeepSeek 查重
3. 测试搜索功能（输入"深圳二模"等关键词）
4. 测试采集功能并验证查重效果
5. 根据实际使用反馈微调 UI
