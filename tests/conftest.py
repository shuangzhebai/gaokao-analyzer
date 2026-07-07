"""测试隔离夹具：在每次测试前清空 slowapi 的内存限速计数。

问题背景：slowapi 的 Limiter 使用模块级内存存储（app.state.limiter），
整轮 pytest 进程中同一 client 主机（"testclient"）的请求共享 200/min 额度。
若某个用例（如 test_rate_limit）耗尽额度，后续访问 app 的用例会因被限流
而收到 429，导致与限速无关的用例（如安全头检查期望 200）误失败。

修复方式：autouse 夹具在每个测试开始前重置限速计数，使各用例互不干扰、
结果确定（与执行顺序无关）。无 slowapi 时 limiter 为 None，跳过重置。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """每个测试前清空 slowapi 限速计数，保证用例间隔离。"""
    from app import app  # noqa: WPS433 — 仅用于重置共享限速状态

    limiter = getattr(app.state, "limiter", None)
    if limiter is not None:
        limiter.reset()
    yield
