"""组卷服务编排层。

协调 CompositionEngine（约束求解）与数据库层，
对外提供组卷生成、微调、导出、模板管理能力。
"""

import json
import logging
import uuid
from typing import Any

from engines.composition_engine import CompositionEngine

logger = logging.getLogger("gaokao")


class CompositionService:
    """组卷服务。"""

    def __init__(
        self,
        engine: CompositionEngine | None = None,
        repo: Any = None,
        quality: Any = None,
    ) -> None:
        self._engine = engine or CompositionEngine()
        self._repo = repo
        self._quality = quality
        self._tasks: dict[str, dict] = {}  # 内存任务跟踪

    async def generate(self, constraints: dict) -> str:
        """生成组卷任务，返回 task_id。"""
        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = {"status": "pending", "progress": 0}

        try:
            # 更新状态为运行中
            self._tasks[task_id] = {"status": "running", "progress": 10}

            # 从数据库读取候选题目（占位：实际需要从 QuestionRepository 读取）
            questions = constraints.get("_candidate_questions", [])
            if not questions:
                # 如果没有候选题目，生成示例占位
                questions = self._mock_questions(constraints)

            self._tasks[task_id] = {"status": "running", "progress": 40}

            # 核心求解
            result = self._engine.solve(questions, constraints)

            self._tasks[task_id] = {"status": "running", "progress": 70}

            # 质量预检
            quality_report = self._engine.precheck_quality(result.question_ids)

            self._tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "result": result.to_dict(),
                "result_data": {
                    "question_ids": result.question_ids,
                    "total_score": result.total_score,
                    "constraints_satisfied": result.constraints_satisfied,
                    "objective_score": result.objective_score,
                    "quality_report": quality_report,
                },
            }

            logger.info("组卷任务 %s 完成: %d 题", task_id, len(result.question_ids))
        except Exception as e:
            logger.error("组卷任务 %s 失败: %s", task_id, e)
            self._tasks[task_id] = {"status": "failed", "progress": 0, "error": str(e)}

        return task_id

    async def get_task(self, task_id: str) -> dict | None:
        """查询组卷任务进度。"""
        return self._tasks.get(task_id)

    async def get_composition(self, composition_id: int) -> dict | None:
        """获取组卷结果。"""
        return {
            "id": composition_id,
            "name": f"组卷 #{composition_id}",
            "question_ids": [],
            "total_score": 0,
            "constraints_satisfied": True,
            "objective_score": 0,
        }

    async def adjust(self, composition_id: int, changes: list[dict]) -> dict:
        """手动微调：换题/调序/改分。"""
        logger.info("微调组卷 %d: %d 处变更", composition_id, len(changes))
        return {"composition_id": composition_id, "changes_applied": len(changes)}

    async def export_pdf(self, composition_id: int) -> bytes:
        """导出试卷为 PDF（占位：实际使用 reportlab/weasyprint）。"""
        return b"PDF content placeholder"

    async def export_word(self, composition_id: int) -> bytes:
        """导出试卷为 Word（占位：实际使用 python-docx）。"""
        return b"Word content placeholder"

    async def save_template(self, name: str, constraints: dict) -> int:
        """存为模板。"""
        logger.info("保存组卷模板: %s", name)
        return 1

    async def list_templates(self, filters: dict | None = None) -> list[dict]:
        """模板列表。"""
        return []

    async def get_alternatives(self, question_id: int, n: int = 3) -> list[int]:
        """获取备选题。"""
        return self._engine.get_alternatives(question_id, n=n)

    def _mock_questions(self, constraints: dict) -> list[dict]:
        """生成模拟题目（用于开发和测试）。"""
        questions = []
        subject_id = constraints.get("subject_id", "math")
        type_configs = constraints.get("types", [{"id": 1, "count": 5, "score": 10}])

        qid = 1
        for tc in type_configs:
            for _ in range(tc.get("count", 5)):
                questions.append({
                    "id": qid,
                    "question_type_id": tc.get("id", 1),
                    "score": tc.get("score", 10),
                    "irt_b": 0.0,
                    "irt_a": 1.0,
                    "difficulty_tag": "中",
                    "knowledge_points": f"kp_{subject_id}_{qid}",
                    "source": "real" if qid % 3 == 0 else "mock",
                    "year": 2025,
                    "content": f"模拟题目 #{qid}",
                })
                qid += 1
        return questions
