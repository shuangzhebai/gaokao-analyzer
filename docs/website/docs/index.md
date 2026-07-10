---
sidebar_position: 1
slug: /
---

# gaokao-analyzer

> **高考教育领域的开源心理测量引擎 + 智能组卷平台**
>
> IRT 3PL/GPCM/GRM · 题型自动分类 · 6 维质量诊断 · OR-Tools 智能组卷 · 错题闭环 · PostgreSQL

高考模拟卷智能分析系统——面向高考教研场景的下一代试卷量化评估与智能组卷平台。**与学科网、组卷网、菁优网等竞品的核心差异在于 IRT 心理测量引擎壁垒**——竞品全部基于 CTT 经典统计，而本系统支持 IRT 3PL/GPCM/GRM 多模型 + Numba JIT 加速。

## v6.0 新增能力

| 模块 | 技术实现 | 说明 |
|------|---------|------|
| 🏷️ **题型自动分类** | 规则引擎 + LightGBM | 9 大学科题型自动识别（选择/填空/解答/综合） |
| 📊 **6 维质量诊断** | IRT+CTT 混合模型 | 难度/区分度/信度/效度/知识点覆盖/题型匹配 + 雷达图 |
| 📝 **智能组卷** | OR-Tools CP-SAT 约束求解 | 按知识点/难度/题型多条件约束自动组卷 + 质量预检报告 |
| ❌ **错题闭环** | 自动收录→IRT诊断→同类推荐 | 薄弱知识点定位 + 精准推题 |
| 👥 **三端工作台** | 学生/教师/教研员角色差异 | 各自仪表盘 + 全链路交互 |
| 📊 **标准化监控** | Prometheus Counter/Histogram/Gauge | 可选 Grafana 面板 |

## 快速开始

### Docker 一键启动（推荐）

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer
docker compose up -d
# 访问 http://localhost:8000
# 管理员账号 admin/admin123 已自动创建
```

### 生产部署

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# 需设置环境变量：
# GAOKAO_ENV=prod
# JWT_SECRET=<强随机密钥>
# API_KEY=<强随机密钥>
```

### 本地开发

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app:app --host 0.0.0.0 --port 8000
pytest tests/ -q  # 289 passed
```

## 核心能力

| 模块 | 技术 | 对比竞品 |
|------|------|---------|
| **IRT 心理测量** | 3PL / GPCM / GRM + Numba JIT | **独家** — 竞品全无 IRT |
| **题型自动分类** | 规则引擎 + LightGBM | 学科网需人工标注，本系统自动 |
| **质量诊断** | IRT+CTT 6 维雷达图 | 竞品仅 1-2 维统计标签 |
| **智能组卷** | OR-Tools CP-SAT 多目标优化 | 竞品为标签匹配贪心算法 |
| **错题管理** | IRT θ 诊断 + 知识图谱 | 竞品缺 IRT 薄弱点定位 |
| **成绩模拟** | 蒙特卡洛 10 万考生 + 偏态校准 | 匹配真实高考分布 |
| **全文搜索** | Meilisearch + FTS5 | 中文分词 + 模糊纠错 |
| **多源采集** | 可插拔适配器（7+ 源） | 学科网/组卷网/菁优网 |
| **标准化监控** | Prometheus 指标 | 可对接 Grafana |

## 技术栈

| 领域 | 技术 |
|------|------|
| 后端 | Python 3.13+ / FastAPI |
| 数据库 | PostgreSQL（主库）/ SQLite（开发退路） |
| 前端 | React 18 + TypeScript + MUI v6 + ECharts |
| 心理测量 | IRT 3PL / GPCM / GRM + OR-Tools |
| 缓存/队列 | Redis + Celery |
| 搜索引擎 | Meilisearch |
| 部署 | Docker Compose + Helm Chart |
| 监控 | Prometheus |
| 测试 | pytest（289 tests, 0 failed） |
