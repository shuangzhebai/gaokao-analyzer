"""题型库编排层 — QuestionService。

协调 QuestionClassifier（分类引擎）与 QuestionRepository（数据访问），
对外提供题型库 CRUD + 分类落库 + 题型树查询能力。
"""

import json
import logging
from typing import Any

from engines.question_classifier import QuestionClassifier
from models import get_db
from services.db_repository import QuestionRepository

logger = logging.getLogger("gaokao")


class QuestionService:
    """题型库编排服务。"""

    def __init__(
        self,
        question_repo: QuestionRepository | None = None,
        classifier: QuestionClassifier | None = None,
    ) -> None:
        self._repo = question_repo or QuestionRepository(db=None)  # type: ignore[arg-type]
        self._classifier = classifier or QuestionClassifier()

    async def _ensure_db(self) -> Any:
        """获取数据库连接并绑定到 repository。"""
        db_gen = get_db()
        db = await db_gen.__anext__()
        self._repo.db = db
        return db

    async def get_question(self, question_id: int) -> dict | None:
        """获取单题详情。"""
        db = await self._ensure_db()
        try:
            question = await self._repo.get(question_id)
            if question:
                # 获取题型信息
                q_type_id = question.get("question_type_id")
                if q_type_id:
                    cursor = await db.execute(
                        "SELECT * FROM question_types WHERE id = ?", (q_type_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        question["question_type"] = dict(row)
            return question
        finally:
            await db.close()

    async def list_questions(
        self,
        filters: dict | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """条件查询题目列表。"""
        db = await self._ensure_db()
        try:
            return await self._repo.list(filters or {}, page=page, size=size)
        finally:
            await db.close()

    async def create_question(self, question_data: dict) -> int:
        """创建题目（自动分类）。"""
        db = await self._ensure_db()
        try:
            # 自动分类
            result = self._classifier.classify(question_data)
            main_type = result["main_type"]
            sub_type = result["sub_type"]

            # 查找或创建 question_type 记录
            q_type_id = await self._resolve_question_type(
                db,
                subject_id=question_data.get("subject_id", ""),
                main_type=main_type,
                sub_type=sub_type,
            )

            # 设置分类信息
            question_data["question_type_id"] = q_type_id
            if "q_type" not in question_data or not question_data["q_type"]:
                question_data["q_type"] = main_type

            return await self._repo.create(question_data)
        finally:
            await db.close()

    async def update_question(self, question_id: int, question_data: dict) -> bool:
        """更新题目。"""
        db = await self._ensure_db()
        try:
            return await self._repo.update(question_id, question_data)
        finally:
            await db.close()

    async def delete_question(self, question_id: int) -> bool:
        """删除题目。"""
        db = await self._ensure_db()
        try:
            return await self._repo.delete(question_id)
        finally:
            await db.close()

    async def classify_question(self, question_data: dict) -> dict:
        """仅分类，不保存。"""
        return self._classifier.classify(question_data)

    async def batch_classify(self, questions_data: list[dict]) -> list[dict]:
        """批量分类。"""
        return self._classifier.batch_classify(questions_data)

    async def classify_and_save(self, question_data: dict) -> int:
        """分类并保存题目（同 create_question 的别名）。"""
        return await self.create_question(question_data)

    async def batch_classify_and_save(self, questions_data: list[dict]) -> list[int]:
        """批量分类并保存。"""
        ids: list[int] = []
        for q_data in questions_data:
            q_id = await self.create_question(q_data)
            ids.append(q_id)
        return ids

    async def get_question_types(self, subject_id: str | None = None) -> list[dict]:
        """获取题型树（从 question_types 表读取）。"""
        db = await self._ensure_db()
        try:
            if subject_id:
                cursor = await db.execute(
                    "SELECT * FROM question_types WHERE subject_id = ? ORDER BY level, id",
                    (subject_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM question_types ORDER BY subject_id, level, id"
                )
            rows = await cursor.fetchall()
            types_list = [dict(r) for r in rows]

            # 构建树结构
            type_map: dict[int, dict] = {}
            tree: list[dict] = []
            for t in types_list:
                t["children"] = []
                type_map[t["id"]] = t
            for t in types_list:
                parent_id = t.get("parent_id")
                if parent_id and parent_id in type_map:
                    type_map[parent_id]["children"].append(t)
                else:
                    tree.append(t)
            return tree
        finally:
            await db.close()

    async def get_quality_summary(self, question_id: int) -> dict | None:
        """单题质量摘要（IRT 参数 / CTT 指标）。"""
        db = await self._ensure_db()
        try:
            cursor = await db.execute(
                """SELECT id, irt_a, irt_b, irt_c, discrimination,
                          irt_params_cache, difficulty_tag, quality_rating
                   FROM questions WHERE id = ?""",
                (question_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            result = dict(row)
            # 解析缓存的 IRT 参数
            cache_raw = result.get("irt_params_cache")
            if cache_raw:
                try:
                    result["irt_params"] = json.loads(cache_raw)
                except (json.JSONDecodeError, TypeError):
                    result["irt_params"] = None
            return result
        finally:
            await db.close()

    async def _resolve_question_type(
        self,
        db: Any,
        subject_id: str,
        main_type: str,
        sub_type: str,
    ) -> int:
        """根据 subject_id + main_type + sub_type 查找或创建 question_type 记录。"""
        cursor = await db.execute(
            """SELECT id FROM question_types
               WHERE subject_id = ? AND main_type = ? AND sub_type = ?""",
            (subject_id, main_type, sub_type)
        )
        row = await cursor.fetchone()
        if row:
            return row["id"]

        # 创建新的题型记录
        name_cn = f"{subject_id}_{main_type}_{sub_type}"
        cursor = await db.execute(
            """INSERT INTO question_types (subject_id, main_type, sub_type, name_cn, level)
               VALUES (?, ?, ?, ?, 2)""",
            (subject_id, main_type, sub_type, name_cn)
        )
        return cursor.lastrowid
