---
sidebar_position: 4
---

# 部署

## Docker Compose（推荐）

```bash
git clone https://github.com/shuangzhebai/gaokao-analyzer.git
cd gaokao-analyzer
docker compose up -d
```

启动后：
- **Web 服务**: http://localhost:8000
- **Redis**: localhost:6379
- **Meilisearch**: http://localhost:7700
- **API 文档**: http://localhost:8000/docs

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CORS_ORIGINS` | `*` | CORS 白名单（逗号分隔） |
| `API_KEY` | 空 | API Key 鉴权（空=不启用） |
| `JWT_SECRET` | `change-me-in-production` | JWT 签名密钥 |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 连接 |
| `MEILISEARCH_URL` | `http://meilisearch:7700` | Meilisearch 连接 |
| `GAOKAO_ENV` | `dev` | 运行环境 |

### 数据持久化

- 数据库：挂载 `./data:/app/data`（SQLite 文件）
- Redis：命名卷 `redis_data`
- Meilisearch：命名卷 `meili_data`

## 裸机部署

```bash
# 环境：Python 3.13+
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Nginx 反向代理示例

```nginx
server {
    listen 443 ssl;
    server_name analyzer.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
