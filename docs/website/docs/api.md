---
sidebar_position: 3
---

# API 参考

所有端点同时支持 `/api/v1/*` 与旧路径 `/api/*`。完整 OpenAPI 文档：启动后访问 `/docs`。

## 认证

### 注册

```bash
POST /api/v1/auth/register
Content-Type: application/x-www-form-urlencoded

username=admin&password=P@ssw0rd&role=admin
```

### 登录

```bash
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=P@ssw0rd
# 返回 { "token": "eyJ...", "token_type": "bearer", "user": {...} }
```

## 试卷

### 列表

```bash
GET /api/v1/papers?subject=math&page=1&size=20
Authorization: Bearer <TOKEN>
```

### 详情

```bash
GET /api/v1/papers/{id}
```

### 上传

```bash
POST /api/v1/papers/upload
Authorization: Bearer <TOKEN>
Content-Type: multipart/form-data

file=@paper.pdf&title=2026模拟卷&subject=math
```

## 分析

### IRT 估计

```bash
POST /api/v1/papers/{id}/simulate
```

### 批量模拟

```bash
POST /api/v1/papers/batch/simulate
Content-Type: application/json

{ "n_students": 50000, "subject": "math" }
```

## 搜索

```bash
GET /api/v1/search?q=函数导数&subject=math&sort=relevance
```

## 任务状态（Celery 异步）

```bash
GET /api/v1/tasks/{task_id}
```
