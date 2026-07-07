"""P0 基线验证：安全响应头 + 运行时上下文 app.state.ctx。

本测试通过 fastapi.testclient.TestClient 触发 lifespan（同时完成引擎初始化、
app.state.ctx 构建），并对 `/api/health` 发起请求，断言：
1. 四个安全响应头（HSTS / X-Content-Type-Options / X-Frame-Options / Referrer-Policy）
   均按预期值挂载；
2. app.state.ctx 字段正确（version / engine_count / deepseek_enabled / started_at /
   python_version / data_dir / db_path / cors_origins / env）；
3. 依赖注入 get_app_context 返回与 app.state.ctx 同一个对象。

纯 pytest，无需 pytest-asyncio；TestClient 内部驱动 lifespan。
"""
import os
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402  — 注意：无 slowapi 环境下应走降级路径
from config import VERSION  # noqa: E402
from deps import get_app_context  # noqa: E402


EXPECTED_SECURITY_HEADERS = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


class TestSecurityHeaders:
    """安全响应头必须在所有响应中出现且值正确。"""

    def test_security_headers_present_on_health(self):
        with TestClient(app) as client:
            resp = client.get("/api/health")
            assert resp.status_code in (200, 401) or resp.status_code == 200 or resp.ok, (
                f"unexpected status {resp.status_code}"
            )
            # 健康检查即使业务态为 error 也应返回 200（见 app.health_check）
            assert resp.status_code == 200, f"health status={resp.status_code}"
            for key, value in EXPECTED_SECURITY_HEADERS.items():
                assert key in resp.headers, f"缺少安全头 {key}"
                assert resp.headers[key] == value, (
                    f"安全头 {key} 值错误: 期望 {value!r}, 实际 {resp.headers[key]!r}"
                )

    def test_security_headers_present_on_root(self):
        with TestClient(app) as client:
            resp = client.get("/")
            assert resp.status_code == 200, f"root status={resp.status_code}"
            for key, value in EXPECTED_SECURITY_HEADERS.items():
                assert key in resp.headers, f"缺少安全头 {key}"
                assert resp.headers[key] == value


class TestAppContext:
    """运行时上下文 app.state.ctx 字段应当正确。"""

    def test_ctx_exists_and_fields_correct(self):
        with TestClient(app) as client:
            ctx = client.app.state.ctx
            assert ctx is not None, "app.state.ctx 未构建"

            # version 来自 config.VERSION
            assert ctx.version == VERSION
            assert ctx.version == "5.1", f"version 期望 5.1, 实际 {ctx.version!r}"

            # 14 个引擎单例已注入
            assert ctx.engine_count == 14, f"engine_count 期望 14, 实际 {ctx.engine_count}"

            # deepseek_enabled 为 bool
            assert isinstance(ctx.deepseek_enabled, bool), (
                f"deepseek_enabled 应为 bool, 实际 {type(ctx.deepseek_enabled)}"
            )

            # started_at 为 ISO 字符串且可解析
            assert isinstance(ctx.started_at, str) and ctx.started_at
            # 解析 ISO 字符串（带时区）不应抛异常
            datetime.fromisoformat(ctx.started_at)

            # 其余字段均非空
            for field in ("python_version", "data_dir", "db_path", "cors_origins", "env"):
                value = getattr(ctx, field)
                assert isinstance(value, str) and value, f"ctx.{field} 为空: {value!r}"

    def test_get_app_context_returns_same_object(self):
        with TestClient(app) as client:
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [],
                "app": client.app,
            }
            request = Request(scope)
            ctx_via_dep = get_app_context(request)
            assert ctx_via_dep is client.app.state.ctx, (
                "get_app_context 未返回 app.state.ctx 同一对象"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
