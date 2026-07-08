---
sidebar_position: 1
slug: /
---

# gaokao-analyzer

> IRT 3PL 参数估计 · 蒙特卡洛模拟 · 6 维度质量分析 · DeepSeek 真实性审核

高考模拟卷智能分析系统——面向高考教研场景的 SAT/ACT 级别试卷量化评估工具。

## 快速开始

### Docker 部署

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer
docker compose up -d
# 访问 http://localhost:8000
```

### 注册管理员

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -d "username=admin&password=P@ssw0rd&role=admin"
```

### 登录获取 Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -d "username=admin&password=P@ssw0rd"
# 返回: {"token": "eyJ...", "token_type": "bearer", ...}
```

### 调用 API

```bash
curl "http://localhost:8000/api/v1/papers" \
  -H "Authorization: Bearer <TOKEN>"
```

### 本地开发

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app:app --host 0.0.0.0 --port 8000
pytest tests/ -q  # 179 passed
```

## 核心能力

| 模块 | 技术 | 精度 |
|------|------|------|
| IRT 参数估计 | 3PL 模型 + MLE | 难度/区分度/猜测参数 |
| 成绩模拟 | 蒙特卡洛 10 万考生 | 偏态校准 + 真实成绩对标 |
| 质量分析 | 6 维度加权 | 信度/效度/区分度/难度/知识点覆盖/题型分布 |
| 真实性审核 | DeepSeek AI + 多源交叉验证 | 99%+ 识别率 |
| 全文搜索 | Meilisearch + SQLite FTS5 降级 | 中文分词 + 高亮 + 纠错 |
| 多源采集 | 可插拔适配器架构 | 学科网/组卷网/菁优网/高考网等 7+ 源 |
