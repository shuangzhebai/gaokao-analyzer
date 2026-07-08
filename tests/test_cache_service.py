"""P1-01: Redis 缓存层测试 — L1 LRU + Redis 降级路径。"""

from unittest.mock import AsyncMock, patch

import pytest

from services.cache_service import CacheService


class TestCacheServiceL1:
    """L1 进程内 LRU 功能测试。"""

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        cs = CacheService()
        await cs.set("test_key", "hello")
        val = await cs.get("test_key")
        assert val == "hello"

    @pytest.mark.asyncio
    async def test_get_missing_key(self) -> None:
        cs = CacheService()
        val = await cs.get("nonexistent")
        assert val is None

    @pytest.mark.asyncio
    async def test_set_dict_value(self) -> None:
        cs = CacheService()
        await cs.set("dict_key", {"a": 1, "b": 2})
        val = await cs.get("dict_key")
        assert val is not None
        assert '"a": 1' in val or "'a': 1" in val

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        cs = CacheService()
        await cs.set("del_key", "value")
        await cs.delete("del_key")
        val = await cs.get("del_key")
        assert val is None


class TestCacheServiceL1Eviction:
    """L1 LRU 淘汰逻辑测试。"""

    @pytest.mark.asyncio
    async def test_max_entries_eviction(self) -> None:
        cs = CacheService()
        cs._max_l1 = 5
        for i in range(10):
            await cs.set(f"key_{i}", f"val_{i}")
        # 应至少淘汰 5 个
        assert len(cs._l1) <= 5

    @pytest.mark.asyncio
    async def test_expired_entry_deleted(self) -> None:
        import time

        cs = CacheService()
        cs._l1["expired_key"] = ("val", time.time() - 10)
        val = await cs.get("expired_key")
        assert val is None
        assert "expired_key" not in cs._l1


class TestCacheServiceRedisDegradation:
    """Redis 不可用时降级为纯 L1 的测试。"""

    @pytest.mark.asyncio
    async def test_service_works_without_redis(self) -> None:
        """即使 Redis 未安装/不可用，CacheService 仍然正常工作。"""
        import services.cache_service as cs_mod

        # 确保模块级状态重置
        saved_redis = cs_mod._HAS_REDIS
        cs_mod._HAS_REDIS = False
        try:
            cs = CacheService()
            await cs.set("no_redis_key", "works")
            val = await cs.get("no_redis_key")
            assert val == "works"
        finally:
            cs_mod._HAS_REDIS = saved_redis
