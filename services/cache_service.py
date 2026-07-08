"""P1-01: Redis 双级缓存（L1 进程 LRU + L2 Redis），Redis 不可用时自动降级为纯 L1。"""

import json
import logging
import os
import time
from typing import Any

from config import REDIS_URL

logger = logging.getLogger(__name__)

_HAS_REDIS: bool = False
_redis_client: Any = None


def _init_redis() -> None:
    """初始化 Redis 连接。若连接失败则优雅降级。"""
    global _HAS_REDIS, _redis_client
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        _redis_client = client
        _HAS_REDIS = True
        logger.info("Redis cache connected — L2 缓存已就绪")
    except Exception as e:
        logger.warning("Redis unavailable, using in-process LRU only: %s", e)
        _HAS_REDIS = False


async def _close_redis() -> None:
    """关闭 Redis 连接（lifespan shutdown 时调用）。"""
    global _redis_client, _HAS_REDIS
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning("Redis 关闭失败: %s", e)
        _redis_client = None
    _HAS_REDIS = False


class CacheService:
    """L1 (进程内 LRU) + L2 (Redis) 双级缓存。"""

    def __init__(self) -> None:
        self._l1: dict[str, tuple[str, float]] = {}
        self._max_l1: int = 256

    def _get_l1(self, key: str) -> str | None:
        """从 L1 读取；过期则删除。"""
        entry = self._l1.get(key)
        if entry is None:
            return None
        val, expires = entry
        if time.time() < expires:
            return val
        del self._l1[key]
        return None

    def _set_l1(self, key: str, value: str, ttl: int = 300) -> None:
        """写入 L1；满时淘汰最早过期项。"""
        if len(self._l1) >= self._max_l1:
            oldest = min(self._l1, key=lambda k: self._l1[k][1])
            del self._l1[oldest]
        self._l1[key] = (value, time.time() + ttl)

    async def get(self, key: str) -> str | None:
        """读取缓存：L1 → L2 → None。"""
        l1_val = self._get_l1(key)
        if l1_val is not None:
            return l1_val
        if _HAS_REDIS and _redis_client is not None:
            try:
                val: str | None = await _redis_client.get(key)
                if val is not None:
                    self._set_l1(key, val, 60)
                    return val
            except Exception:
                logger.warning("Redis get(%s) 失败", key)
        return None

    async def set(self, key: str, value: str | dict[str, Any], ttl: int = 0) -> None:
        """写入缓存（L1 + L2）。"""
        if ttl <= 0:
            ttl = int(os.environ.get("CACHE_TTL", "300"))
        payload: str
        if isinstance(value, dict):
            payload = json.dumps(value, ensure_ascii=False, default=str)
        else:
            payload = value
        self._set_l1(key, payload, min(ttl, 60))
        if _HAS_REDIS and _redis_client is not None:
            try:
                await _redis_client.set(key, payload, ex=ttl)
            except Exception:
                logger.warning("Redis set(%s) 失败", key)

    async def delete(self, key: str) -> None:
        """删除缓存条目。"""
        self._l1.pop(key, None)
        if _HAS_REDIS and _redis_client is not None:
            try:
                await _redis_client.delete(key)
            except Exception:
                logger.warning("Redis delete(%s) 失败", key)


# 模块级单例
_cache_service: CacheService | None = None


async def init_cache() -> CacheService:
    """lifespan 启动时调用：初始化 Redis 连接 + 创建 CacheService 单例。"""
    global _cache_service
    if _cache_service is None:
        _init_redis()
        _cache_service = CacheService()
    return _cache_service


def get_cache() -> CacheService:
    """获取 CacheService 单例（需确保已调用 init_cache）。"""
    if _cache_service is None:
        raise RuntimeError("CacheService not initialized. Call init_cache() in lifespan first.")
    return _cache_service
