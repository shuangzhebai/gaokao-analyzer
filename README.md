# gaokao-analyzer

> 高考模拟卷智能分析系统 — 基于 IRT 参数估计与偏态分布模拟

## 功能特性

- **模拟引擎 v5.1**：分位数匹配 + 偏态正态分布 + 混合考生群体，模拟真实高考成绩分布
- **试卷采集**：自动从多个权威来源采集试卷，支持交叉验证
- **真实性审核**：6 维度审核（地区/来源/题目完整性/分值/IRT参数/难度校准）
- **多维搜索**：支持省份、考试标签、关键词（智能分词 + AND/OR 降级）
- **官方文件库**：预置课程标准/考试大纲等权威文件
- **液态玻璃 UI**：Apple Design 风格，backdrop-filter 毛玻璃效果

## 技术栈

- **后端**：FastAPI + SQLite (aiosqlite) + NumPy + SciPy
- **前端**：原生 HTML/CSS/JS + Chart.js
- **数据**：IRT (Item Response Theory) 参数估计

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用（首次运行自动初始化数据库）
python start.py

# 重建数据库（重置所有数据）
python start.py --reset
```

访问 http://127.0.0.1:8899

## 目录结构

```
gaokao-analyzer/
├── app.py              # FastAPI 主应用
├── analyzer.py        # 试卷分析逻辑
├── simulator.py       # 成绩模拟引擎
├── search.py          # 多维搜索引擎
├── scraper.py         # 试卷采集器
├── auto_scraper.py    # 自动采集调度
├── auth_verifier.py   # 真实性审核
├── official_docs.py   # 官方文件库
├── region_validator.py# 地区校验引擎
├── sample_data.py     # 样本数据生成
├── config.py          # 配置文件
├── models.py          # 数据模型
├── parser.py          # 试卷解析
├── start.py           # 启动入口
└── static/
    └── index.html     # 前端页面
```

## 许可证

MIT License
