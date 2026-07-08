"""Celery 应用实例 — Redis broker + result backend。

Celery worker 启动命令：celery -A celery_app worker --loglevel=info
"""

import logging
import os

logger = logging.getLogger(__name__)

_HAS_CELERY: bool = False
app: object | None = None  # Celery 应用实例，类型擦除以避免 mypy strict 对 celery 的复杂类型检查


def _create_app():
    """创建 Celery 应用实例（模块加载时惰性执行）。"""
    global app, _HAS_CELERY
    if app is not None:
        return
    try:
        from celery import Celery as CeleryApp

        broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
        backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

        celery = CeleryApp(
            "gaokao_analyzer",
            broker=broker_url,
            backend=backend_url,
        )
        celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="Asia/Shanghai",
            enable_utc=True,
            task_track_started=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
        )
        app = celery
        _HAS_CELERY = True
        logger.info("Celery 已就绪 (broker=%s, backend=%s)", broker_url, backend_url)

        # 自动发现任务模块
        celery.autodiscover_tasks(["tasks"])
    except Exception as e:
        logger.warning("Celery 不可用，异步任务将降级为同步执行: %s", e)
        _HAS_CELERY = False


# 模块加载时即创建（Celery worker 也需要 app 实例）
_create_app()
