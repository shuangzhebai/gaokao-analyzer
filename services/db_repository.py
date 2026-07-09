"""数据访问层 — Repository 模式。

所有数据库操作通过 Repository 类进行，业务层不直接执行 SQL。
当前基于 aiosqlite（SQLite）实现，统一通过 db_service 提供的连接进行操作。
"""

from __future__ import annotations

from typing import Any


class BaseRepository:
    """Repository 基类，定义标准 CRUD 接口。"""

    def __init__(self, db: Any) -> None:
        self.db = db  # 数据库连接（aiosqlite 或 asyncpg 包装）

    async def get(self, id: int) -> dict | None:
        """按 ID 查询单条记录。"""
        raise NotImplementedError

    async def list(self, filters: dict, page: int = 1, size: int = 20) -> dict:
        """条件查询，返回 {data, total, page, size}。"""
        raise NotImplementedError

    async def create(self, data: dict) -> int:
        """创建记录，返回新 ID。"""
        raise NotImplementedError

    async def update(self, id: int, data: dict) -> bool:
        """更新记录，返回是否成功。"""
        raise NotImplementedError

    async def delete(self, id: int) -> bool:
        """删除记录，返回是否成功。"""
        raise NotImplementedError


class QuestionRepository(BaseRepository):
    """题库 Repository。"""

    async def get(self, id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM questions WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list(self, filters: dict, page: int = 1, size: int = 20) -> dict:
        where_clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if key in ("subject_id", "question_type_id", "source", "year"):
                where_clauses.append(f"{key} = ?")
                params.append(value)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        offset = (page - 1) * size
        cursor = await self.db.execute(
            f"SELECT * FROM questions WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, size, offset)
        )
        rows = await cursor.fetchall()
        total_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM questions WHERE {where_sql}", params
        )
        total = (await total_cursor.fetchone())[0]
        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    async def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = await self.db.execute(
            f"INSERT INTO questions ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        return cursor.lastrowid

    async def update(self, id: int, data: dict) -> bool:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        cursor = await self.db.execute(
            f"UPDATE questions SET {set_clause} WHERE id = ?",
            (*data.values(), id)
        )
        return cursor.rowcount > 0

    async def delete(self, id: int) -> bool:
        cursor = await self.db.execute("DELETE FROM questions WHERE id = ?", (id,))
        return cursor.rowcount > 0

    # 题库特有方法
    async def search_by_knowledge(self, kp_codes: list[str]) -> list[dict]:
        """按知识点代码搜索题目（knowledge_points 字段模糊匹配）。"""
        results: list[dict] = []
        for code in kp_codes:
            cursor = await self.db.execute(
                "SELECT * FROM questions WHERE knowledge_points LIKE ?",
                (f"%{code}%",)
            )
            rows = await cursor.fetchall()
            results.extend(dict(r) for r in rows)
        # 去重
        seen: set[int] = set()
        unique: list[dict] = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        return unique

    async def get_real_exam_questions(self, subject_id: str, year_range: tuple[int, int]) -> list[dict]:
        """获取高考真题。"""
        cursor = await self.db.execute(
            "SELECT * FROM questions WHERE subject_id = ? AND source = 'real' AND year BETWEEN ? AND ? ORDER BY year DESC",
            (subject_id, year_range[0], year_range[1])
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def batch_get_irt_params(self, ids: list[int]) -> dict[int, dict]:
        """批量获取 IRT 参数。"""
        placeholders = ",".join(["?"] * len(ids))
        cursor = await self.db.execute(
            f"SELECT id, irt_a, irt_b, irt_c, discrimination, irt_params_cache FROM questions WHERE id IN ({placeholders})",
            ids
        )
        rows = await cursor.fetchall()
        return {r["id"]: dict(r) for r in rows}


class ErrorRepository(BaseRepository):
    """错题库 Repository（占位，T05 实现）。"""

    async def get(self, id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM error_records WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list(self, filters: dict, page: int = 1, size: int = 20) -> dict:
        where_clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if key in ("user_id", "subject_id", "error_reason", "is_mastered"):
                where_clauses.append(f"{key} = ?")
                params.append(value)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        offset = (page - 1) * size
        cursor = await self.db.execute(
            f"SELECT * FROM error_records WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, size, offset)
        )
        rows = await cursor.fetchall()
        total_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM error_records WHERE {where_sql}", params
        )
        total = (await total_cursor.fetchone())[0]
        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    async def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = await self.db.execute(
            f"INSERT INTO error_records ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        return cursor.lastrowid

    async def update(self, id: int, data: dict) -> bool:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        cursor = await self.db.execute(
            f"UPDATE error_records SET {set_clause} WHERE id = ?",
            (*data.values(), id)
        )
        return cursor.rowcount > 0

    async def delete(self, id: int) -> bool:
        cursor = await self.db.execute("DELETE FROM error_records WHERE id = ?", (id,))
        return cursor.rowcount > 0


class ProfileRepository(BaseRepository):
    """学生画像 Repository（占位，T05 实现）。"""

    async def get(self, id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM student_profiles WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_by_user_subject(self, user_id: int, subject_id: str) -> dict | None:
        """按 user_id + subject_id 查询。"""
        cursor = await self.db.execute(
            "SELECT * FROM student_profiles WHERE user_id = ? AND subject_id = ?",
            (user_id, subject_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list(self, filters: dict, page: int = 1, size: int = 20) -> dict:
        where_clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if key in ("user_id", "subject_id"):
                where_clauses.append(f"{key} = ?")
                params.append(value)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        offset = (page - 1) * size
        cursor = await self.db.execute(
            f"SELECT * FROM student_profiles WHERE {where_sql} ORDER BY last_updated DESC LIMIT ? OFFSET ?",
            (*params, size, offset)
        )
        rows = await cursor.fetchall()
        total_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM student_profiles WHERE {where_sql}", params
        )
        total = (await total_cursor.fetchone())[0]
        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    async def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = await self.db.execute(
            f"INSERT INTO student_profiles ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        return cursor.lastrowid

    async def update(self, id: int, data: dict) -> bool:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        cursor = await self.db.execute(
            f"UPDATE student_profiles SET {set_clause} WHERE id = ?",
            (*data.values(), id)
        )
        return cursor.rowcount > 0

    async def delete(self, id: int) -> bool:
        cursor = await self.db.execute("DELETE FROM student_profiles WHERE id = ?", (id,))
        return cursor.rowcount > 0


class PaperTemplateRepository(BaseRepository):
    """组卷模板 Repository。"""

    async def get(self, id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM paper_templates WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list(self, filters: dict, page: int = 1, size: int = 20) -> dict:
        where_clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if key in ("subject_id", "is_public", "created_by"):
                where_clauses.append(f"{key} = ?")
                params.append(value)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        offset = (page - 1) * size
        cursor = await self.db.execute(
            f"SELECT * FROM paper_templates WHERE {where_sql} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (*params, size, offset)
        )
        rows = await cursor.fetchall()
        total_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM paper_templates WHERE {where_sql}", params
        )
        total = (await total_cursor.fetchone())[0]
        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    async def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = await self.db.execute(
            f"INSERT INTO paper_templates ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        return cursor.lastrowid

    async def update(self, id: int, data: dict) -> bool:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        cursor = await self.db.execute(
            f"UPDATE paper_templates SET {set_clause} WHERE id = ?",
            (*data.values(), id)
        )
        return cursor.rowcount > 0

    async def delete(self, id: int) -> bool:
        cursor = await self.db.execute("DELETE FROM paper_templates WHERE id = ?", (id,))
        return cursor.rowcount > 0


class CompositionRecordRepository(BaseRepository):
    """组卷记录 Repository。"""

    async def get(self, id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM composition_records WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list(self, filters: dict, page: int = 1, size: int = 20) -> dict:
        where_clauses: list[str] = []
        params: list[Any] = []
        for key, value in filters.items():
            if key in ("subject_id", "status", "created_by", "template_id"):
                where_clauses.append(f"{key} = ?")
                params.append(value)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        offset = (page - 1) * size
        cursor = await self.db.execute(
            f"SELECT * FROM composition_records WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, size, offset)
        )
        rows = await cursor.fetchall()
        total_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM composition_records WHERE {where_sql}", params
        )
        total = (await total_cursor.fetchone())[0]
        return {
            "data": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }

    async def create(self, data: dict) -> int:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = await self.db.execute(
            f"INSERT INTO composition_records ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        return cursor.lastrowid

    async def update(self, id: int, data: dict) -> bool:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        cursor = await self.db.execute(
            f"UPDATE composition_records SET {set_clause} WHERE id = ?",
            (*data.values(), id)
        )
        return cursor.rowcount > 0

    async def delete(self, id: int) -> bool:
        cursor = await self.db.execute("DELETE FROM composition_records WHERE id = ?", (id,))
        return cursor.rowcount > 0

    # T04: 组卷专用方法
    async def create_composition(
        self, name: str, subject_id: str, created_by: str, constraints_json: str
    ) -> int:
        """创建组卷记录。"""
        cursor = await self.db.execute(
            "INSERT INTO composition_records (name, subject_id, created_by, constraints_json) VALUES (?, ?, ?, ?)",
            (name, subject_id, created_by, constraints_json)
        )
        return cursor.lastrowid

    async def update_result(
        self, id: int, question_ids_json: str, quality_report_json: str, status: str
    ) -> None:
        """更新组卷结果。"""
        await self.db.execute(
            "UPDATE composition_records SET question_ids_json=?, quality_report_json=?, status=? WHERE id=?",
            (question_ids_json, quality_report_json, status, id)
        )
