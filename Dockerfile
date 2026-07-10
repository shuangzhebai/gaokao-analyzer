# 高考模拟卷智能分析系统 - 运行镜像
# 基于 python:3.13-slim；使用系统 pip 安装依赖（不把 .venv 打进镜像）。
FROM python:3.13-slim

WORKDIR /app

# 先复制依赖清单并安装，利用 Docker 层缓存（源码改动不会使该层失效）。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    # 健康检查依赖 curl
    apt-get update -qq && apt-get install -y -qq curl && rm -rf /var/lib/apt/lists/*

# 复制应用源码（.venv 已被 .dockerignore 排除）
COPY . .

# 应用监听端口（与 docker-compose 映射一致）
EXPOSE 8000

# 说明：start.py 的 __main__ 还会执行耗时的样例数据生成并绑定 127.0.0.1:8899，
# 不适合容器端口映射；而 lifespan 已在启动时执行 init_db() + seed_data()，
# 因此直接使用 uvicorn 启动即可（0.0.0.0:8000）。
# 运行期调参：CORS_ORIGINS / API_KEY / GAOKAO_ENV / PYTHONUNBUFFERED（见 compose）。
# 数据库位于 /app/data，compose 挂载 ./data:/app/data 实现持久化。
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
