"""测试隔离夹具：在每次测试前清空 slowapi 的内存限速计数。
仅在有 FastAPI 依赖时自动启用；缺失时跳过不阻塞其他纯逻辑测试。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """每个测试前清空 slowapi 限速计数，保证用例间隔离。
    若无 FastAPI 环境（如纯逻辑测试），跳过此夹具。
    """
    try:
        from app import app  # noqa: WPS433
        limiter = getattr(app.state, "limiter", None)
        if limiter is not None:
            limiter.reset()
    except (ImportError, ModuleNotFoundError, AttributeError):
        pass  # 纯逻辑测试无需重置限速器
    yield
