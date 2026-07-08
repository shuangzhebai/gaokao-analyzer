"""
T05 测试：API 版本化 + JWT+RBAC 鉴权 + CORS 白名单。

测试范围：
1. API 版本化：/api/v1/ 端点可达，旧 /api/ 路径保持兼容
2. 注册用户 → 成功
3. 登录 → 返回 JWT token
4. 用 token 访问受保护端点 → 200
5. 无 token 访问写端点 → 401（API_KEY 未设置时）
6. 无效 token → 401
7. API Key 兼容模式（设置 API_KEY 后使用 API Key 访问）→ 200
8. CORS 头检查
9. 角色鉴权测试
10. 健康检查在 /api/health 和 /api/v1/health 均可访问
"""
import json
import os
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 预设 API_KEY 环境变量供兼容模式测试
_TEST_API_KEY = "test-api-key-12345"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """每个测试前清空 slowapi 限速计数，保证用例间隔离。"""
    from app import app  # noqa: WPS433

    limiter = getattr(app.state, "limiter", None)
    if limiter is not None:
        limiter.reset()
    yield


class TestAPIVersioning:
    """API 版本化：新老路径均可访问。"""

    def setup_method(self):
        self._clear_api_key_env()

    def _clear_api_key_env(self):
        """清除 API_KEY 环境变量，使中间件不拦截请求。"""
        os.environ.pop("API_KEY", None)

    def test_v1_health_endpoint(self):
        """/api/v1/health 端点可正常响应。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    def test_old_health_endpoint(self):
        """旧 /api/health 端点仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    def test_v1_subjects_endpoint(self):
        """/api/v1/subjects 返回科目列表。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/subjects")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0
            assert any(s["id"] == "math" for s in data)

    def test_old_subjects_endpoint(self):
        """旧 /api/subjects 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/subjects")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0

    def test_v1_filters_endpoint(self):
        """/api/v1/filters 可访问。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/filters")
            assert resp.status_code == 200

    def test_old_filters_endpoint(self):
        """旧 /api/filters 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/filters")
            assert resp.status_code == 200

    def test_v1_regions_endpoint(self):
        """/api/v1/regions 可访问。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/regions")
            assert resp.status_code == 200

    def test_old_regions_endpoint(self):
        """旧 /api/regions 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/regions")
            assert resp.status_code == 200

    def test_v1_dashboard_endpoint(self):
        """/api/v1/dashboard 可访问。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/dashboard")
            assert resp.status_code == 200

    def test_old_dashboard_endpoint(self):
        """旧 /api/dashboard 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/dashboard")
            assert resp.status_code == 200

    def test_v1_search_endpoint(self):
        """/api/v1/search 可访问（无查询参数返回空结果）。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/search")
            # search 可能返回空结果或者错误，只要不是 404/500 即可
            assert resp.status_code in (200, 422)

    def test_old_search_endpoint(self):
        """旧 /api/search 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/search")
            assert resp.status_code in (200, 422)


class TestAuthRegister:
    """用户注册测试。"""

    def setup_method(self):
        self._clear_api_key_env()
        self._cleanup_test_users()

    def _clear_api_key_env(self):
        os.environ.pop("API_KEY", None)

    def _cleanup_test_users(self):
        """清理测试用户。"""
        from config import DB_PATH

        try:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'test_%')")
                conn.execute("DELETE FROM users WHERE username LIKE 'test_%'")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass

    def test_register_success(self):
        """注册新用户成功。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/register",
                params={"username": "test_user_1", "password": "SecurePass123!", "role": "viewer"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert data["user"]["username"] == "test_user_1"
            assert data["user"]["role"] == "viewer"
            assert "id" in data["user"]

    def test_register_duplicate(self):
        """注册重复用户名应返回 400。"""
        from app import app

        with TestClient(app) as client:
            # 第一次注册成功
            resp1 = client.post(
                "/api/v1/auth/register",
                params={"username": "test_user_dup", "password": "SecurePass123!", "role": "viewer"},
            )
            assert resp1.status_code == 200

            # 重复注册失败
            resp2 = client.post(
                "/api/v1/auth/register",
                params={"username": "test_user_dup", "password": "AnotherPass456!", "role": "viewer"},
            )
            assert resp2.status_code == 400

    def test_register_invalid_role(self):
        """注册时使用无效角色应返回 400。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/register",
                params={"username": "test_user_bad_role", "password": "SecurePass123!", "role": "superadmin"},
            )
            assert resp.status_code == 400

    def test_register_with_email(self):
        """注册时带邮箱。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/register",
                params={"username": "test_user_email", "password": "SecurePass123!", "email": "test@example.com"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True

    def test_register_old_path(self):
        """旧路径 /api/auth/register 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/auth/register",
                params={"username": "test_user_old_path", "password": "SecurePass123!"},
            )
            assert resp.status_code == 200


class TestAuthLogin:
    """用户登录测试。"""

    def setup_method(self):
        self._clear_api_key_env()
        self._cleanup_test_users()
        self._create_test_user()

    def _clear_api_key_env(self):
        os.environ.pop("API_KEY", None)

    def _cleanup_test_users(self):
        from config import DB_PATH

        try:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'test_%')")
                conn.execute("DELETE FROM users WHERE username LIKE 'test_%'")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass

    def _create_test_user(self):
        from app import app

        with TestClient(app) as client:
            client.post(
                "/api/v1/auth/register",
                params={"username": "test_login_user", "password": "SecurePass123!", "role": "teacher"},
            )

    def test_login_success(self):
        """登录成功返回 token。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                params={"username": "test_login_user", "password": "SecurePass123!"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["username"] == "test_login_user"
            assert data["user"]["role"] == "teacher"

    def test_login_wrong_password(self):
        """密码错误应返回 401。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                params={"username": "test_login_user", "password": "WrongPassword!"},
            )
            assert resp.status_code == 401

    def test_login_nonexistent_user(self):
        """不存在的用户登录应返回 401。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/auth/login",
                params={"username": "nonexistent_user", "password": "SecurePass123!"},
            )
            assert resp.status_code == 401

    def test_login_old_path(self):
        """旧路径 /api/auth/login 仍然可用。"""
        from app import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/auth/login",
                params={"username": "test_login_user", "password": "SecurePass123!"},
            )
            assert resp.status_code == 200


class TestJWTAuth:
    """JWT 令牌鉴权测试。"""

    def setup_method(self):
        self._clear_api_key_env()
        self._cleanup_test_users()
        self._create_test_user()

    def _clear_api_key_env(self):
        os.environ.pop("API_KEY", None)

    def _cleanup_test_users(self):
        from config import DB_PATH

        try:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute(
                    "DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'test_%')"
                )
                conn.execute("DELETE FROM users WHERE username LIKE 'test_%'")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass

    def _create_test_user(self):
        from app import app

        with TestClient(app) as client:
            client.post(
                "/api/v1/auth/register",
                params={"username": "test_jwt_user", "password": "SecurePass123!", "role": "admin"},
            )

    def _login_and_get_token(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            params={"username": "test_jwt_user", "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_token_works_for_write_endpoint(self):
        """使用有效 JWT token 可访问 POST 端点（API_KEY 未设置时）。"""
        from app import app

        with TestClient(app) as client:
            token = self._login_and_get_token(client)
            # 尝试访问一个 POST 端点
            resp = client.post(
                "/api/v1/papers/99999/analyze",
                headers={"Authorization": f"Bearer {token}"},
            )
            # 试卷不存在应返回 404，而不是 401
            assert resp.status_code in (404, 405)

    def test_no_token_returns_401_on_write(self):
        """无 token 访问 POST 端点应返回 401（当 API_KEY 已设置时）。"""
        import importlib

        os.environ["API_KEY"] = _TEST_API_KEY
        try:
            import app as app_module
            import services.auth_service

            importlib.reload(services.auth_service)
            importlib.reload(app_module)
            app = app_module.app

            with TestClient(app) as client:
                resp = client.post("/api/v1/papers/99999/analyze")
                assert resp.status_code == 401
        finally:
            os.environ.pop("API_KEY", None)

    def test_invalid_token_returns_401(self):
        """无效 JWT token 在 API_KEY 设置时应返回 401。"""
        import importlib

        os.environ["API_KEY"] = _TEST_API_KEY
        try:
            import app as app_module
            import services.auth_service

            importlib.reload(services.auth_service)
            importlib.reload(app_module)
            app = app_module.app

            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/papers/99999/analyze",
                    headers={"Authorization": "Bearer invalid-token-xxx"},
                )
                assert resp.status_code == 401
        finally:
            os.environ.pop("API_KEY", None)


class TestAPIKeyCompatibility:
    """旧 API Key 兼容模式测试。

    注意：API_KEY 是 app.py 的模块级变量，首次导入后缓存。
    使用 importlib.reload 强制重新加载模块以读取新环境变量。
    """

    def setup_method(self):
        os.environ["API_KEY"] = _TEST_API_KEY

    def teardown_method(self):
        os.environ.pop("API_KEY", None)

    def _reload_app(self):
        """强制重新加载 app 模块以读取当前环境变量。"""
        import importlib
        import app as app_module
        import services.auth_service
        importlib.reload(services.auth_service)
        importlib.reload(app_module)
        return app_module.app

    def test_api_key_works_for_write(self):
        """使用 API Key 可访问 POST 端点。"""
        app = self._reload_app()

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/papers/99999/analyze",
                headers={"Authorization": f"Bearer {_TEST_API_KEY}"},
            )
            # 试卷不存在
            assert resp.status_code in (404, 405)

    def test_wrong_api_key_returns_401(self):
        """错误的 API Key 应返回 401。"""
        app = self._reload_app()

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/papers/99999/analyze",
                headers={"Authorization": "Bearer wrong-api-key"},
            )
            assert resp.status_code == 401

    def test_no_auth_header_returns_401(self):
        """无 Authorization 头应返回 401。"""
        app = self._reload_app()

        with TestClient(app) as client:
            resp = client.post("/api/v1/papers/99999/analyze")
            assert resp.status_code == 401

    def test_get_endpoint_without_auth(self):
        """GET 端点不需要鉴权（即使 API_KEY 已设置）。"""
        app = self._reload_app()

        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200


class TestCORSHeaders:
    """CORS 响应头测试。"""

    def test_cors_headers_present(self):
        """所有响应应包含 CORS 头。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/health",
                headers={"Origin": "http://localhost:5173"},
            )
            assert resp.status_code == 200
            # allow_origins=["*"] + allow_credentials=True 时，
            # CORSMiddleware 会 echo 请求的 Origin 而非返回 *
            cors_origin = resp.headers.get("access-control-allow-origin", "")
            assert cors_origin == "http://localhost:5173"

    def test_cors_with_credentials(self):
        """CORS allow-credentials 为 true。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/health",
                headers={"Origin": "http://localhost:5173"},
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-credentials") == "true"


class TestHealthEndpoints:
    """健康检查端点测试。"""

    def setup_method(self):
        os.environ.pop("API_KEY", None)

    def test_old_health_works(self):
        """旧 /api/health 端点正常。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200

    def test_v1_health_works(self):
        """/api/v1/health 端点正常。"""
        from app import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200

    def test_both_health_return_same_structure(self):
        """两个健康检查端点返回一致的结构。"""
        from app import app

        with TestClient(app) as client:
            resp_old = client.get("/api/health")
            resp_v1 = client.get("/api/v1/health")
            assert resp_old.status_code == 200
            assert resp_v1.status_code == 200
            data_old = resp_old.json()
            data_v1 = resp_v1.json()
            assert data_old["status"] == data_v1["status"]
            assert data_old["version"] == data_v1["version"]


class TestRoleBasedAccess:
    """基于角色的访问控制测试。"""

    def setup_method(self):
        self._clear_api_key_env()
        self._cleanup_test_users()
        self._create_test_users()

    def _clear_api_key_env(self):
        os.environ.pop("API_KEY", None)

    def _cleanup_test_users(self):
        from config import DB_PATH

        try:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute(
                    "DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'test_%')"
                )
                conn.execute("DELETE FROM users WHERE username LIKE 'test_%'")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass

    def _create_test_users(self):
        from app import app

        with TestClient(app) as client:
            client.post(
                "/api/v1/auth/register",
                params={"username": "test_role_admin", "password": "AdminPass123!", "role": "admin"},
            )
            client.post(
                "/api/v1/auth/register",
                params={"username": "test_role_viewer", "password": "ViewerPass123!", "role": "viewer"},
            )

    def _login(self, client, username: str, password: str) -> str:
        resp = client.post(
            "/api/v1/auth/login",
            params={"username": username, "password": password},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_token_contains_role(self):
        """JWT token 应包含角色信息。"""
        from app import app

        with TestClient(app) as client:
            token = self._login(client, "test_role_admin", "AdminPass123!")
            # 解码 token 验证 role
            from jose import jwt as jose_jwt
            from config import JWT_SECRET, JWT_ALGORITHM

            payload = jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            assert payload["role"] == "admin"
            assert payload["username"] == "test_role_admin"
