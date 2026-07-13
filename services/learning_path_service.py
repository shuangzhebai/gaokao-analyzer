"""学习路径服务 — CRUD + 进度追踪"""
from __future__ import annotations
from datetime import datetime
import json
from typing import Optional


class LearningPathService:
    def __init__(self, repo):
        self.repo = repo

    async def create(self, user_id: int, subject_id: str, session_id: str,
                      plan_json: dict) -> int:
        """创建学习路径"""
        return await self.repo.execute(
            """INSERT INTO learning_paths
               (user_id, subject_id, session_id, plan_json)
               VALUES (?, ?, ?, ?)""",
            user_id, subject_id, session_id,
            json.dumps(plan_json, ensure_ascii=False),
        )

    async def get_list(self, user_id: int, subject_id: Optional[str] = None,
                        status: Optional[str] = None) -> list[dict]:
        """查询用户学习路径列表"""
        where = ["user_id = ?"]
        params = [user_id]
        if subject_id:
            where.append("subject_id = ?")
            params.append(subject_id)
        if status:
            where.append("status = ?")
            params.append(status)
        return await self.repo.query(
            f"SELECT * FROM learning_paths WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            *params,
        )

    async def get_detail(self, path_id: int, user_id: int) -> Optional[dict]:
        """获取学习路径详情"""
        rows = await self.repo.query(
            "SELECT * FROM learning_paths WHERE id = ? AND user_id = ?",
            path_id, user_id,
        )
        if rows:
            row = rows[0]
            if isinstance(row.get("plan_json"), str):
                row["plan_json"] = json.loads(row["plan_json"])
            return row
        return None

    async def update_progress(self, path_id: int, user_id: int,
                               progress_pct: float) -> None:
        """更新进度百分比"""
        await self.repo.execute(
            "UPDATE learning_paths SET progress_pct = ?, updated_at = datetime('now') WHERE id = ? AND user_id = ?",
            progress_pct, path_id, user_id,
        )

    async def update_status(self, path_id: int, user_id: int,
                             status: str) -> None:
        """更新状态"""
        await self.repo.execute(
            "UPDATE learning_paths SET status = ?, updated_at = datetime('now') WHERE id = ? AND user_id = ?",
            status, path_id, user_id,
        )

    async def delete(self, path_id: int, user_id: int) -> None:
        """废弃学习路径"""
        await self.update_status(path_id, user_id, "abandoned")

    async def get_overall_progress(self, user_id: int, subject_id: str) -> dict:
        """获取学习总览数据（仪表盘用）"""
        # 活跃学习路径
        active_paths = await self.get_list(user_id, subject_id, "active")
        current_path = active_paths[0] if active_paths else None

        # 已完成路径数
        completed = await self.repo.query(
            "SELECT COUNT(*) as cnt FROM learning_paths WHERE user_id = ? AND status = 'completed'",
            user_id,
        )

        return {
            "has_active_path": current_path is not None,
            "current_path": current_path,
            "completed_paths": completed[0]["cnt"] if completed else 0,
            "total_paths": len(active_paths) + (completed[0]["cnt"] if completed else 0),
        }
