"""
P0 基线验证：操作审计日志（audit_log）。
与 verification_audit（试卷真实性审核）完全独立。

测试策略：
- 使用 fastapi.testclient.TestClient 发送 HTTP 请求，触发审计中间件
- 使用同步 sqlite3 直接查询 audit_log 表验证记录写入
- setup_method 清空审计日志表以保证测试隔离
"""
import os
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402
from config import DB_PATH  # noqa: E402


def _count_audit_logs() -> int:
    """同步查询 audit_log 表中的记录数。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM audit_log")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def _get_audit_logs() -> list[dict]:
    """同步查询 audit_log 表全部记录，按时间倒序。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


class TestAuditLog:
    """操作审计日志功能测试"""

    def setup_method(self):
        """每个测试前清空审计日志表，保证用例间隔离。
        注：setup_method 在 TestClient 触发 lifespan 之前运行，
        此时 audit_log 表可能尚不存在（由 init_db 创建），
        因此使用 try/except 忽略表不存在的错误。
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute("DELETE FROM audit_log")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass  # 表尚未创建，TestClient lifespan 会处理

    def test_post_creates_audit_record(self):
        """POST 请求后 audit_log 表中出现对应记录。"""
        with TestClient(app) as client:
            # POST 到不存在试卷的分析端点（预期 404），审计中间件会记录
            resp = client.post("/api/papers/99999/analyze")
            # 只要请求被中间件处理即可，404/405 均为正常状态
            assert resp.status_code in (404, 405)

            logs = _get_audit_logs()
            assert len(logs) >= 1, "POST 后应产生审计记录"
            assert logs[0]["action"] == "POST"
            assert logs[0]["user"] == "anonymous"

    def test_get_does_not_trigger_audit(self):
        """GET 请求不触发审计。"""
        with TestClient(app) as client:
            # 确保初始状态为空
            self.setup_method()

            resp = client.get("/api/health")
            assert resp.status_code == 200

            count = _count_audit_logs()
            assert count == 0, "GET 不应产生审计记录"

    def test_health_check_path_skipped(self):
        """健康检查路径即使 POST 也被跳过。"""
        with TestClient(app) as client:
            self.setup_method()

            # POST 到健康检查路径（方法不允许，但中间件应先于路由判断运行）
            resp = client.post("/api/health")
            assert resp.status_code == 405  # POST 方法不允许

            count = _count_audit_logs()
            assert count == 0, "健康检查路径应被审计跳过"

    def test_audit_fields_correct(self):
        """审计记录包含正确的 action / resource_type / resource_id / ip 字段。"""
        with TestClient(app) as client:
            self.setup_method()

            resp = client.post("/api/papers/99999/analyze")
            assert resp.status_code in (404, 405)

            logs = _get_audit_logs()
            assert len(logs) >= 1

            record = logs[0]
            assert record["action"] == "POST"
            # resource_type 从路径倒数第二部分推断
            assert record["resource_type"] in ("papers", "99999")
            assert record["user"] == "anonymous"
            # user_agent 字段应非空（TestClient 会发送默认 UA）
            assert record["user_agent"] is not None

    def test_post_with_delete_method(self):
        """DELETE 请求也触发审计。"""
        with TestClient(app) as client:
            self.setup_method()

            resp = client.delete("/api/papers/99999")
            assert resp.status_code in (404, 405)

            logs = _get_audit_logs()
            assert len(logs) >= 1
            assert logs[0]["action"] == "DELETE"

    def test_list_recent_method(self):
        """AuditService 的 list_recent 方法正常工作返回最近记录。"""
        with TestClient(app) as client:
            self.setup_method()

            # 先产生两条审计记录
            client.post("/api/papers/99999/analyze")
            client.delete("/api/papers/88888")

            # 通过 app.state 获取 audit_service 并调用 list_recent
            audit_service = client.app.state.audit_service
            assert audit_service is not None, "audit_service 应已被中间件惰性初始化"

            # 使用异步包装查询
            import asyncio
            import aiosqlite

            async def _query():
                db = await aiosqlite.connect(DB_PATH)
                db.row_factory = aiosqlite.Row

                # 添加与 models.get_db 一致的包装方法
                _orig_execute = db.execute

                async def _execute_fetchone(sql, params=None):
                    cursor = await _orig_execute(sql, params or [])
                    row = await cursor.fetchone()
                    return dict(row) if row else None

                async def _execute_fetchall(sql, params=None):
                    cursor = await _orig_execute(sql, params or [])
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

                db.execute_fetchone = _execute_fetchone
                db.execute_fetchall = _execute_fetchall

                try:
                    rows = await audit_service.list_recent(db, limit=10)
                    assert len(rows) >= 2, f"应有 ≥2 条记录，实际 {len(rows)}"
                    assert rows[0]["action"] in ("POST", "DELETE")
                    # 按时间倒序，最近的在最前
                    assert rows[0]["resource_type"] in ("papers", "99999")
                finally:
                    await db.close()

            asyncio.run(_query())
