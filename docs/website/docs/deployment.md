---
sidebar_position: 4
---

# 部署

## Docker Compose 本地部署（快速启动）

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer
docker compose up -d
```

启动后：
- **Web 服务**: http://localhost:8000（管理员 admin/admin123 已自动创建）
- **Redis**: localhost:6379
- **Meilisearch**: http://localhost:7700
- **API 文档**: http://localhost:8000/docs
- **Prometheus 指标**: http://localhost:8000/metrics

## Docker Compose 生产部署

```bash
# 设置安全凭证
export JWT_SECRET=$(openssl rand -hex 32)
export API_KEY=$(openssl rand -hex 32)

# 启动（启用 PostgreSQL + 生产安全策略）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

生产模式 (`GAOKAO_ENV=prod`) 自动启用：
- JWT_SECRET/API_KEY 缺失→拒绝启动（fail-fast）
- PostgreSQL 主数据库
- CORS 白名单严格校验
- 容器健康检查

## Helm Chart（K8s 部署）

```bash
helm install gaokao-analyzer deploy/charts/gaokao-analyzer \
  --set config.corsOrigins="https://app.example.com"
```

Chart 包含：Deployment / Service / Ingress / ConfigMap / Celery Worker。

## 裸机部署

```bash
# 环境：Python 3.13+
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

pip install -r requirements.txt
# 可选：启用 OR-Tools 智能组卷（pip install ortools）
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GAOKAO_ENV` | `dev` | 运行环境（dev/prod）。prod 启用安全强制 |
| `GAOKAO_DB` | `sqlite` | 数据库后端（sqlite/postgresql） |
| `DATABASE_URL` | — | PG 连接串（`postgresql://user:pass@host:5432/db`） |
| `JWT_SECRET` | 临时密钥（dev） | JWT 签名密钥（prod **必须设置**） |
| `JWT_REFRESH_SECRET` | 同 JWT_SECRET | Refresh Token 签名密钥（可选独立设置） |
| `API_KEY` | 空（dev 无鉴权） | API 写接口鉴权（prod **必须设置**） |
| `CORS_ORIGINS` | dev: 本地端口白名单 | CORS 白名单（逗号分隔） |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 连接 |
| `MEILISEARCH_URL` | `http://meilisearch:7700` | Meilisearch 连接 |
| `IRT_PREHEAT` | `true` | 启动时预热 IRT 参数缓存 |
| `WEBHOOK_SECRET` | 空 | Webhook HMAC-SHA256 签名密钥 |
| `TOKEN_BLACKLIST_ENABLED` | `true` | JWT 黑名单吊销 |

### 数据持久化

- **SQLite 模式**：挂载 `./data:/app/data`
- **PostgreSQL 模式**：使用命名卷 `pg_data` 或绑定额外的数据目录
- Redis：命名卷 `redis_data`
- Meilisearch：命名卷 `meili_data`

## Nginx 反向代理示例

```nginx
server {
    listen 443 ssl;
    server_name analyzer.example.com;

    client_max_body_size 50M;  # 试卷上传可能较大

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 一键启动（Windows 无 Docker）

双击 **`一键启动.bat`** 或 **`Docker一键启动.bat`**：

```bash
# 一键启动.bat — 自动创建虚拟环境、安装依赖、启动服务、打开浏览器
# Docker一键启动.bat — Docker 方式启动
```
