"""P0 基线验证：全局 API 速率限制（slowapi default_limits=["200/minute"]）。

前置条件：venv 已安装 slowapi（>=0.1.9）。安装后 `import app` 会令
``app._HAS_SLOWAPI = True``，并在 app 上注册 limiter 与 SlowAPIMiddleware。

本测试通过 TestClient 对 `/api/health` 连续发起 205 次请求（同一分钟内快速循环），
在循环前调用 ``limiter.reset()`` 清空内存计数，确保窗口从 0 开始、结果确定。
全局默认 200/min 意味着第 1..200 次返回 200，第 201..205 次应被限流返回 429。
因此断言：至少出现一次 429。

若 venv 未安装 slowapi，则本测试降级为验证「import app 仍成功且未注册 limiter」。
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as app_module  # noqa: E402

pytestmark = pytest.mark.skipif(
    not getattr(app_module, "_HAS_SLOWAPI", False),
    reason="slowapi 未安装，限速中间件未注册（降级路径）；见 test_rate_limit_fallback",
)


class TestRateLimit:
    """全局默认 200/min 必须对超出请求返回 429。"""

    def test_exceeds_200_per_minute_returns_429(self):
        with TestClient(app_module.app) as client:
            limiter = getattr(client.app.state, "limiter", None)
            assert limiter is not None, "limiter 未注册（slowapi 路径异常）"
            # 清空内存计数，确保本测试从 0 开始一个干净的 200/min 窗口
            limiter.reset()

            n_requests = 205
            statuses = []
            for _ in range(n_requests):
                resp = client.get("/api/health")
                statuses.append(resp.status_code)

            n_429 = sum(1 for s in statuses if s == 429)
            n_200 = sum(1 for s in statuses if s == 200)

            assert n_429 >= 1, (
                f"连续 {n_requests} 次请求未触发任何 429，限速未生效；"
                f"statuses 分布: 200={n_200}, 429={n_429}"
            )
            # 前 200 次应在额度内（200），之后被限流（429）
            assert n_200 >= 200, f"200 响应数异常（期望>=200）: {n_200}"
            assert n_429 == n_requests - 200, (
                f"429 数量应为 {n_requests - 200}，实际 {n_429}"
            )


class TestRateLimitFallback:
    """未安装 slowapi 时的降级路径：import 成功且不注册 limiter。"""

    def test_no_slowapi_import_ok_and_no_limiter(self):
        # 无论是否安装 slowapi，import app 都不应抛异常
        assert app_module._HAS_SLOWAPI in (True, False)
        if not app_module._HAS_SLOWAPI:
            with TestClient(app_module.app) as client:
                assert getattr(client.app.state, "limiter", None) is None
