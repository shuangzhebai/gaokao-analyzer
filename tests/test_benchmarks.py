"""
性能基准测试（差距项 #8：pytest-benchmark）。

运行: .venv/Scripts/python -m pytest tests/test_benchmarks.py --benchmark-only -q
CI 门禁: .venv/Scripts/python -m pytest tests/test_benchmarks.py --benchmark-compare --benchmark-warmup-iterations=1
"""

import pytest


# ============ 数据库查询基准 ============

class TestDBBenchmarks:
    """数据库操作基准。——"""

    @pytest.mark.benchmark(min_rounds=10, warmup=True)
    def test_db_connect(self, benchmark) -> None:
        """数据库连接建立耗时。"""
        import asyncio
        from services.db_service import get_db_backend, close_db

        async def _run():
            db = await get_db_backend("sqlite")
            await db.execute("SELECT 1")
            await close_db(db)
        benchmark(asyncio.run, _run())

    @pytest.mark.benchmark(min_rounds=50, warmup=True)
    def test_simple_query(self, benchmark) -> None:
        """简单查询耗时 (SELECT COUNT)。"""
        import asyncio
        from models import get_db

        async def _run():
            async for db in get_db():
                await db.execute_fetchone("SELECT COUNT(*) as cnt FROM papers")
        benchmark(asyncio.run, _run())

    @pytest.mark.benchmark(min_rounds=20, warmup=True)
    def test_fts_search(self, benchmark) -> None:
        """FTS5 全文搜索基准。"""
        import asyncio
        from models import get_db

        async def _run():
            async for db in get_db():
                await db.execute_fetchall(
                    "SELECT rowid, rank FROM papers_fts WHERE papers_fts MATCH ? ORDER BY rank LIMIT 10",
                    ['"数学"']
                )
        benchmark(asyncio.run, _run())


# ============ IRT 算法基准 ============

class TestIRTBenchmarks:
    """IRT 算法性能基准。"""

    @pytest.mark.benchmark(min_rounds=5, warmup=True)
    def test_simulate_10000(self, benchmark) -> None:
        """10K 考生蒙特卡洛模拟（50 题）。"""
        import asyncio
        import numpy as np
        from analyzer import IRTModel

        irt = IRTModel()
        item_params = [
            {"a": 1.0 + np.random.random() * 0.5,
             "b": np.random.normal(0, 1),
             "c": np.random.random() * 0.3}
            for _ in range(50)
        ]
        n = 10000

        async def _run():
            thetas = np.random.normal(0, 1, n)
            import numpy as np
            prob = np.zeros((n, 50))
            for j, p in enumerate(item_params):
                prob[:, j] = irt.icc_vectorized(thetas, p["a"], p["b"], p["c"])
            return prob

        benchmark(asyncio.run, _run())

    @pytest.mark.benchmark(min_rounds=5, warmup=True)
    def test_simulate_numba(self, benchmark) -> None:
        """Numba JIT 版 10K 模拟基准（需安装 numba）。"""
        try:
            from simulator import _HAS_NUMBA
            if not _HAS_NUMBA:
                pytest.skip("Numba 未安装")
        except ImportError:
            pytest.skip("Numba 不可用")

        import asyncio
        import numpy as np
        from simulator import _compute_prob_matrix_numba

        n = 10000
        thetas = np.random.normal(0, 1, n)
        a_vals = np.random.uniform(0.8, 1.8, 50)
        b_vals = np.random.normal(0, 1, 50)
        c_vals = np.random.uniform(0, 0.3, 50)

        async def _run():
            return _compute_prob_matrix_numba(thetas, a_vals, b_vals, c_vals)

        benchmark(asyncio.run, _run())


# ============ JSON 序列化基准 ============

class TestJSONBenchmarks:
    """JSON 序列化性能基准（对比标准 json vs orjson）。"""

    SAMPLE_DATA = {
        "status": "ok",
        "papers_count": 1234,
        "data": [{"id": i, "title": f"试卷 {i} 2026年高考模拟卷" * 3} for i in range(100)]
    }

    @pytest.mark.benchmark(min_rounds=100, warmup=True)
    def test_standard_json(self, benchmark) -> None:
        """标准 json.dumps 序列化。"""
        import json
        benchmark(json.dumps, self.SAMPLE_DATA, ensure_ascii=False)

    @pytest.mark.benchmark(min_rounds=100, warmup=True)
    def test_orjson(self, benchmark) -> None:
        """orjson.dumps 序列化（如已安装）。"""
        try:
            import orjson
            benchmark(orjson.dumps, self.SAMPLE_DATA)
        except ImportError:
            pytest.skip("orjson 未安装")
