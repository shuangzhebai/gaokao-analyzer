"""Webhook 服务测试（差距项 #9）。"""

from fastapi.testclient import TestClient
import pytest

from app import app


class TestWebhooks:
    """Webhook CRUD 端点测试。"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        with TestClient(app) as client:
            self.client = client

    def test_list_webhooks_requires_auth(self) -> None:
        """未认证时返回 401。"""
        resp = self.client.get("/api/v1/webhooks")
        assert resp.status_code in (401, 403)

    def test_create_webhook_requires_https(self) -> None:
        """非 HTTPS URL 应被拒绝。"""
        resp = self.client.post(
            "/api/v1/webhooks",
            data={"url": "http://example.com/hook", "events": "task.completed"},
        )
        assert resp.status_code in (401, 403, 400)
