"""
P0 安全三连修复 — 回归验证测试。

测试覆盖：
1. GAOKAO_ENV=prod 且 JWT_SECRET 未设置/为默认值 → config 导入抛 RuntimeError
2. GAOKAO_ENV=prod 且 API_KEY 为空 → app 导入抛 RuntimeError
3. GAOKAO_ENV=dev 默认 → config 正常导入，JWT_SECRET 为临时生成值（非默认值）
4. CORS allow_credentials 在 origins 为空时不应为 True
5. CORS 在 dev 默认配置下应有正确的 origins 和 allow_credentials
6. GAOKAO_ENV=prod 且 JWT_SECRET 已设置 → config 正常导入
7. docker-compose.yml 中的占位值读取验证

注意：config.py 和 app.py 的模块常量在首次导入后缓存，
因此 prod fail-fast 测试使用 subprocess 启动隔离进程验证。
"""
import importlib
import os
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ============================================================
# 辅助函数：在隔离子进程中测试 config/app 导入行为
# ============================================================

def _run_in_isolation(code: str, env_overrides: dict[str, str] | None = None) -> tuple[int, str, str]:
    """在隔离子进程中运行 Python 代码，返回 (returncode, stdout, stderr)。

    环境变量：基线与当前进程一致，env_overrides 覆盖或新增。
    """
    base_env = os.environ.copy()
    if env_overrides:
        # 先移除被显式设为 None/空串的 key（模拟"未设置"）
        for k, v in list(env_overrides.items()):
            if v is None:
                base_env.pop(k, None)
                env_overrides.pop(k)
        base_env.update(env_overrides)

    # 确保 GAOKAO_ENV 在 env_overrides 中
    if env_overrides and "GAOKAO_ENV" not in env_overrides:
        # 如果未指定，从 base_env 取；否则保留
        pass

    # 使用 0-indent 的 wrapper 模板；{code} 由调用方 textwrap.dedent 处理为 0-indent，
    # 再整体用 textwrap.indent 缩进 4 格以放入 try 块内。
    _code_indented = textwrap.indent(code, "    ") if code else ""
    wrapped_code = f"""
import sys
sys.path.insert(0, {ROOT!r})
# 强制清除可能已缓存的模块
for mod in list(sys.modules.keys()):
    if mod.startswith("config") or mod.startswith("app"):
        del sys.modules[mod]
try:
{_code_indented}
except Exception as e:
    print(f"[[EXCEPTION]]:{{type(e).__name__}}:{{e}}", flush=True)
    raise
"""

    result = subprocess.run(
        [sys.executable, "-c", wrapped_code],
        capture_output=True,
        text=True,
        timeout=30,
        env=base_env,
    )
    return result.returncode, result.stdout, result.stderr


# ============================================================
# Test 1: GAOKAO_ENV=prod + JWT_SECRET 未设置 → RuntimeError
# ============================================================

class TestProdJWTSecretNotSet:
    """GAOKAO_ENV=prod 且 JWT_SECRET 未设置 → config.py 导入应抛 RuntimeError。"""

    def test_jwt_secret_unset_raises(self):
        rc, out, err = _run_in_isolation(
            "import config",
            {"GAOKAO_ENV": "prod", "JWT_SECRET": None},
        )
        assert rc != 0, f"预期 config 导入失败，但返回码为 0。stdout={out}, stderr={err}"
        assert "RuntimeError" in out or "RuntimeError" in err, (
            f"预期 RuntimeError，但未找到。stdout={out}, stderr={err}"
        )
        assert "JWT_SECRET" in out + err, (
            f"错误信息应提及 JWT_SECRET。stdout={out}, stderr={err}"
        )

    def test_jwt_secret_default_value_raises(self):
        """prod 下 JWT_SECRET 仍为默认值 'change-me-in-production' 也应抛 RuntimeError。"""
        rc, out, err = _run_in_isolation(
            "import config",
            {"GAOKAO_ENV": "prod", "JWT_SECRET": "change-me-in-production"},
        )
        assert rc != 0, f"预期 config 导入失败(默认值)，但返回码为 0。stdout={out}"
        assert "RuntimeError" in out or "RuntimeError" in err


# ============================================================
# Test 2: GAOKAO_ENV=prod + API_KEY 为空 → app 导入抛 RuntimeError
# ============================================================

class TestProdAPIKeyEmpty:
    """GAOKAO_ENV=prod 且 API_KEY 为空 → app.py 导入应抛 RuntimeError。"""

    def test_api_key_empty_raises(self):
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                import app
            """),
            {"GAOKAO_ENV": "prod", "API_KEY": None, "JWT_SECRET": "prod-secure-key-12345"},
        )
        assert rc != 0, f"预期 app 导入失败，但返回码为 0。stdout={out}"
        assert "RuntimeError" in out or "RuntimeError" in err, (
            f"预期 RuntimeError，但未找到。stdout={out}"
        )
        assert "API_KEY" in out + err, (
            f"错误信息应提及 API_KEY。stdout={out}"
        )

    def test_api_key_empty_no_jwt_secret_also_raises(self):
        """prod 下 API_KEY 和 JWT_SECRET 均未设置：先触发 JWT_SECRET 检测的 RuntimeError。"""
        rc, out, err = _run_in_isolation(
            "import config",
            {"GAOKAO_ENV": "prod", "API_KEY": None, "JWT_SECRET": None},
        )
        assert rc != 0, f"预期导入失败，但返回码为 0。stdout={out}"
        assert "RuntimeError" in out or "RuntimeError" in err


# ============================================================
# Test 3: GAOKAO_ENV=dev 默认 → config 正常导入，JWT_SECRET 为临时生成值
# ============================================================

class TestDevDefaultConfig:
    """GAOKAO_ENV=dev 默认下 config 应正常导入，JWT_SECRET 为临时生成值。"""

    def test_dev_config_imports_ok(self):
        """dev 默认下 config 导入不应抛异常。"""
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                # 确认 GAOKAO_ENV 为 dev
                assert config.GAOKAO_ENV == "dev", f"GAOKAO_ENV={config.GAOKAO_ENV}"
                # JWT_SECRET 不应为默认值
                assert config.JWT_SECRET != "change-me-in-production", \
                    f"JWT_SECRET 仍为默认值: {config.JWT_SECRET}"
                # JWT_SECRET 应为临时生成的随机字符串（长度 >= 32）
                assert len(config.JWT_SECRET) >= 32, \
                    f"JWT_SECRET 过短: {len(config.JWT_SECRET)}"
                # CORS_ORIGINS 应有本地前端来源
                assert len(config.CORS_ORIGINS) > 0, "CORS_ORIGINS 不应为空"
                assert "http://localhost:5173" in config.CORS_ORIGINS, \
                    f"缺少 localhost:5173: {config.CORS_ORIGINS}"
                print("ALL_DEV_CHECKS_PASSED", flush=True)
            """),
            {"GAOKAO_ENV": None},  # 不设置 → 默认 dev
        )
        assert rc == 0, f"dev 默认导入失败: stdout={out}, stderr={err}"
        assert "ALL_DEV_CHECKS_PASSED" in out

    def test_dev_jwt_secret_is_random(self):
        """dev 下 JWT_SECRET 应为临时随机值，非默认值。"""
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                print(config.JWT_SECRET, flush=True)
            """),
            {"GAOKAO_ENV": None},
        )
        assert rc == 0, f"导入失败: stdout={out}"
        jwt = out.strip().split("\n")[-1].strip()
        assert jwt != "change-me-in-production", f"JWT_SECRET 仍为默认值: {jwt}"
        assert len(jwt) >= 32, f"JWT_SECRET 过短: {jwt}"

    def test_dev_jwt_secret_changes_per_process(self):
        """验证每次导入生成不同的 JWT_SECRET。"""
        results = []
        for _ in range(2):
            rc, out, err = _run_in_isolation(
                "import config; print(config.JWT_SECRET, flush=True)",
                {"GAOKAO_ENV": None},
            )
            assert rc == 0
            jwt = out.strip().split("\n")[-1].strip()
            results.append(jwt)
        assert results[0] != results[1], (
            f"两次导入 JWT_SECRET 相同（怀疑缓存）: {results[0]}"
        )

    def test_dev_cors_origins_default(self):
        """dev 下 CORS_ORIGINS 默认应包含本地前端端口。"""
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                expected = [
                    "http://localhost:5173",
                    "http://localhost:3000",
                    "http://localhost:8000",
                    "http://127.0.0.1:5173",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:8000",
                ]
                assert config.CORS_ORIGINS == expected, \
                    f"CORS_ORIGINS 不符:\\n期望: {expected}\\n实际: {config.CORS_ORIGINS}"
                print("CORS_CHECK_PASSED", flush=True)
            """),
            {"GAOKAO_ENV": None},
        )
        assert rc == 0, f"CORS check failed: stdout={out}"
        assert "CORS_CHECK_PASSED" in out


# ============================================================
# Test 4: CORS allow_credentials 在 origins 为空时不应为 True
# ============================================================

class TestCORSCredentialsEmptyOrigins:
    """CORS allow_credentials 在 origins 为空时不应为 True。"""

    def test_prod_empty_origins_no_credentials(self):
        """prod 未设置 CORS_ORIGINS → origins=[], allow_credentials=False。"""
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                from app import app
                # 查找 CORSMiddleware 实例
                for mw in app.user_middleware:
                    if mw.cls.__name__ == "CORSMiddleware":
                        kwargs = mw.kwargs
                        assert kwargs.get("allow_origins") == [], \
                            f"allow_origins={kwargs.get('allow_origins')}"
                        assert kwargs.get("allow_credentials") is False, \
                            f"allow_credentials={kwargs.get('allow_credentials')}"
                        print("CORS_CREDENTIALS_CHECK_PASSED", flush=True)
                        break
                else:
                    raise AssertionError("未找到 CORSMiddleware")
            """),
            {
                "GAOKAO_ENV": "prod",
                "CORS_ORIGINS": None,
                "JWT_SECRET": "prod-secure-key-12345",
                "API_KEY": "prod-api-key-67890",
            },
        )
        assert rc == 0, f"prod CORS check failed: stdout={out}, stderr={err}"
        assert "CORS_CREDENTIALS_CHECK_PASSED" in out


# ============================================================
# Test 5: GAOKAO_ENV=prod 且 JWT_SECRET 已设置 → 正常导入
# ============================================================

class TestProdJWTSecretSet:
    """GAOKAO_ENV=prod 且 JWT_SECRET 已设置 → config 应正常导入。"""

    def test_prod_with_jwt_secret_ok(self):
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                assert config.GAOKAO_ENV == "prod", f"GAOKAO_ENV={config.GAOKAO_ENV}"
                assert config.JWT_SECRET == "my-prod-secret-key-that-is-strong-enough"
                print("PROD_JWT_OK", flush=True)
            """),
            {
                "GAOKAO_ENV": "prod",
                "JWT_SECRET": "my-prod-secret-key-that-is-strong-enough",
            },
        )
        assert rc == 0, f"prod JWT 设置后仍失败: stdout={out}, stderr={err}"
        assert "PROD_JWT_OK" in out

    def test_prod_both_set_ok(self):
        """prod 下 JWT_SECRET + API_KEY 均正确设置 → app 正常导入。"""
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                import app
                assert config.GAOKAO_ENV == "prod"
                assert config.JWT_SECRET == "strong-jwt-secret-for-prod-12345"
                assert app.API_KEY == "strong-api-key-for-prod-67890"
                print("PROD_BOTH_OK", flush=True)
            """),
            {
                "GAOKAO_ENV": "prod",
                "JWT_SECRET": "strong-jwt-secret-for-prod-12345",
                "API_KEY": "strong-api-key-for-prod-67890",
            },
        )
        assert rc == 0, f"prod JWT+API_KEY 正确设置后仍失败: stdout={out}, stderr={err}"
        assert "PROD_BOTH_OK" in out


# ============================================================
# Test 6: app_context.py 中 CORS_ORIGINS 与 GAOKAO_ENV 引用正确
# ============================================================

class TestAppContextIntegration:
    """验证 app_context 中的 cors_origins 和 env 字段来自 config 常量。"""

    def test_app_context_cors_origins_dev(self):
        """dev 下 app_context.cors_origins 应包含 localhost 地址。"""
        from app import app
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            ctx = client.app.state.ctx
            assert ctx is not None
            assert ctx.env == "dev"
            assert "localhost:5173" in ctx.cors_origins
            assert "localhost:3000" in ctx.cors_origins

    def test_app_context_reflects_config(self):
        """验证 app_context 的 cors_origins 与 env 与 config 一致。"""
        from app import app
        import config as cfg
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            ctx = client.app.state.ctx
            assert ctx.env == cfg.GAOKAO_ENV
            # cors_origins 在 app_context 中 join 成字符串
            if cfg.CORS_ORIGINS:
                assert all(o in ctx.cors_origins for o in cfg.CORS_ORIGINS)
            else:
                assert "(deny-all)" in ctx.cors_origins


# ============================================================
# Test 7: CORS 在 dev 情况下 allow_credentials 应为 True
# ============================================================

class TestCORSDevCredentials:
    """dev 默认 CORS 白名单非空且不含 * → allow_credentials 应为 True。"""

    def test_dev_cors_credentials_true(self):
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                from app import app
                for mw in app.user_middleware:
                    if mw.cls.__name__ == "CORSMiddleware":
                        kwargs = mw.kwargs
                        assert kwargs.get("allow_credentials") is True, \
                            f"dev allow_credentials={kwargs.get('allow_credentials')}"
                        assert len(kwargs.get("allow_origins", [])) > 0, \
                            "dev allow_origins 不应为空"
                        print("DEV_CORS_CREDENTIALS_OK", flush=True)
                        break
                else:
                    raise AssertionError("未找到 CORSMiddleware")
            """),
            {},  # 默认 dev
        )
        assert rc == 0, f"dev CORS credentials check failed: stdout={out}, stderr={err}"
        assert "DEV_CORS_CREDENTIALS_OK" in out


# ============================================================
# Test 8: CORS_ORIGINS 含通配符 '*' 时 allow_credentials=False
# ============================================================

class TestCORSWildcardNoCredentials:
    """CORS_ORIGINS 含 '*' 时 allow_credentials 应为 False。"""

    def test_wildcard_disables_credentials(self):
        rc, out, err = _run_in_isolation(
            textwrap.dedent("""\
                import config
                from app import app
                for mw in app.user_middleware:
                    if mw.cls.__name__ == "CORSMiddleware":
                        kwargs = mw.kwargs
                        assert kwargs.get("allow_credentials") is False, \
                            f"通配符下 allow_credentials={kwargs.get('allow_credentials')}"
                        print("WILDCARD_CREDENTIALS_OK", flush=True)
                        break
                else:
                    raise AssertionError("未找到 CORSMiddleware")
            """),
            {
                "CORS_ORIGINS": "*",
                "GAOKAO_ENV": None,  # 即使 dev，显式设为 * 也应禁用 credentials
            },
        )
        assert rc == 0, f"wildcard CORS check failed: stdout={out}, stderr={err}"
        assert "WILDCARD_CREDENTIALS_OK" in out


# ============================================================
# Test 9: docker-compose.yml 占位值验证（确认 API_KEY 非空占位值）
# ============================================================

class TestDockerComposePlaceholder:
    """docker-compose.yml 中的 API_KEY 应为占位值（非空串）。"""

    def test_docker_compose_api_key_not_empty(self):
        """docker-compose 的 API_KEY 占位值非空（区别于空串导致的 prod fail-fast）。"""
        import yaml

        compose_path = os.path.join(ROOT, "docker-compose.yml")
        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        web_env = data["services"]["web"]["environment"]
        api_key = web_env.get("API_KEY", "")
        assert api_key, f"docker-compose API_KEY 为空: {api_key!r}"
        assert api_key != "", "docker-compose API_KEY 不应是空串"
        # 占位值不应是空串（允许"please-set..."这类值）
        assert "please-set" in api_key or len(api_key) > 10, (
            f"docker-compose API_KEY 占位值不合理: {api_key!r}"
        )

        cors_origins = web_env.get("CORS_ORIGINS", "")
        assert cors_origins, f"docker-compose CORS_ORIGINS 不应为空: {cors_origins!r}"

        gaokao_env = web_env.get("GAOKAO_ENV", "")
        assert gaokao_env == "dev", f"GAOKAO_ENV 应为 dev: {gaokao_env!r}"
