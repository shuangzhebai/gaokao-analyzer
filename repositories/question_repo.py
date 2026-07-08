"""
题目 DAO：封装 questions 表的所有 SQL 操作（aiosqlite，不引入 ORM）。
"""
from typing import Any, Optional


_MAX_BATCH_QUESTIONS = 500


class QuestionRepository:
    """题目数据访问对象"""

    async def list_by_paper(self, db: Any, paper_id: int) -> Any:
        """获取某试卷的全部题目，按题号排序"""
        return await db.execute_fetchall(
            "SELECT * FROM questions WHERE paper_id = ? ORDER BY q_number", (paper_id,)
        )

    async def create_batch(self, db: Any, paper_id: int, questions: list[dict[str, Any]]) -> None:
        """批量插入题目（最多 500 条）。"""
        if len(questions) > _MAX_BATCH_QUESTIONS:
            raise ValueError(f"批量插入题目数超过上限 {_MAX_BATCH_QUESTIONS}")
        for q in questions:
            await db.execute(
                """INSERT INTO questions
                   (paper_id, q_number, q_type, content, options, score,
                    knowledge_points, content_hash, answer, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paper_id,
                    q.get("q_number", 0),
                    q.get("q_type", "choice"),
                    q.get("content"),
                    q.get("options"),
                    q.get("score", 0),
                    q.get("knowledge_points"),
                    q.get("content_hash", ""),
                    q.get("answer"),
                    q.get("explanation"),
                ),
            )

    async def update_irt(self, db: Any, q_id: int, a: float, b: float, c: float, disc: float) -> None:
        """更新题目的 IRT 参数"""
        await db.execute(
            "UPDATE questions SET irt_a=?, irt_b=?, irt_c=?, discrimination=? WHERE id=?",
            (a, b, c, disc, q_id),
        )

    async def update_quality(self, db: Any, q_id: int, rating: str, is_quality: int) -> None:
        """更新题目的质量评估"""
        await db.execute(
            "UPDATE questions SET quality_rating=?, is_quality=? WHERE id=?",
            (rating, is_quality, q_id),
        )

    async def update_cognitive(self, db: Any, q_id: int, cognitive: Optional[str], competency: Optional[str]) -> None:
        """更新题目的认知水平和核心素养"""
        await db.execute(
            "UPDATE questions SET cognitive_level=?, core_competency=? WHERE id=?",
            (cognitive, competency, q_id),
        )

    async def get_quality_questions(
        self, db: Any,
        subject: Optional[str] = None,
        q_type: Optional[str] = None,
        limit: int = 50,
    ) -> Any:
        """获取优质题推荐"""
        conditions = ["q.is_quality = 1"]
        params = []
        if subject:
            conditions.append("p.subject_id = ?")
            params.append(subject)
        if q_type:
            conditions.append("q.q_type = ?")
            params.append(q_type)

        where = "WHERE " + " AND ".join(conditions)
        return await db.execute_fetchall(
            f"""SELECT q.*, p.title as paper_title, p.subject_id, p.year, p.province
                FROM questions q JOIN papers p ON q.paper_id = p.id
                {where}
                ORDER BY q.discrimination DESC
                LIMIT ?""",
            params + [limit],
        )

    async def get_by_paper_ids(self, db: Any, paper_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        """批量获取多份试卷的题目，返回 {paper_id: [questions]}（最多 100 份）。"""
        if not paper_ids:
            return {}
        if len(paper_ids) > 100:
            raise ValueError("paper_ids 数量超过上限 100")
        placeholders = ",".join("?" * len(paper_ids))
        rows = await db.execute_fetchall(
            f"SELECT * FROM questions WHERE paper_id IN ({placeholders}) ORDER BY q_number",
            paper_ids,
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for r in rows:
            pid = r["paper_id"]
            if pid not in result:
                result[pid] = []
            result[pid].append(r)
        return result

    async def create(self, db: Any, data: dict[str, Any]) -> Any:
        """插入一条题目记录"""
        cursor = await db.execute(
            """INSERT INTO questions
               (paper_id, q_number, q_type, content, options, score, knowledge_points, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("paper_id"),
                data.get("q_number", 0),
                data.get("q_type", "choice"),
                data.get("content"),
                data.get("options"),
                data.get("score", 0),
                data.get("knowledge_points"),
                data.get("content_hash", ""),
            ),
        )
        return cursor.lastrowid
