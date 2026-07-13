"""Agent 服务适配器 — 桥接Agent与现有Service层"""
from __future__ import annotations
from typing import Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class AgentServiceAdapter:
    """
    统一服务适配器：为4个Agent提供所需的所有Service方法。
    - 现有方法：委托给真实Service
    - 缺失方法：默认实现（可被mock数据覆盖）
    """

    def __init__(self):
        self._student_service = None
        self._error_service = None
        self._question_service = None
        self._composition_service = None
        self._db_repo = None

    def inject(self, *, student=None, error=None, question=None, composition=None, db=None):
        """注入真实Service实例"""
        if student:
            self._student_service = student
        if error:
            self._error_service = error
        if question:
            self._question_service = question
        if composition:
            self._composition_service = composition
        if db:
            self._db_repo = db

    # ============================================================
    # 学生画像
    # ============================================================

    async def get_profile(self, user_id: int, subject_id: str) -> dict:
        """获取学生画像（theta + knowledge_mastery）"""
        if self._student_service:
            try:
                theta = await self._student_service.get_theta(user_id, subject_id)
                # get_profile 方法可能不存在，使用 try/except 兜底
                try:
                    profile = await self._student_service.get_profile(user_id, subject_id)  # type: ignore
                    if isinstance(profile, dict):
                        return profile
                except AttributeError:
                    pass  # StudentProfileService 没有 get_profile 方法
                return {"theta": theta, "knowledge_mastery": {}}
            except Exception as e:
                logger.warning(f"get_profile failed: {e}")

        # Fallback mock
        return {
            "theta": 0.35,
            "theta_se": 0.12,
            "knowledge_mastery": {
                "math_func_basic": 0.72,
                "math_func_composite": 0.23,
                "math_geometry_space": 0.31,
                "math_derivative": 0.55,
                "math_probability": 0.68,
            },
            "total_questions": 120,
            "correct_questions": 78,
        }

    async def update_profile(self, user_id: int, subject_id: str, theta: float,
                              new_weaknesses: list[str] | None = None,
                              resolved_weaknesses: list[str] | None = None) -> None:
        """更新学生画像（测评闭环反馈）"""
        if self._student_service:
            try:
                await self._student_service.update_knowledge_mastery(
                    user_id, subject_id,
                    {w: 0.8 for w in (resolved_weaknesses or [])},
                )
                logger.info(f"Updated profile: user={user_id}, theta={theta:.2f}")
            except Exception as e:
                logger.warning(f"update_profile failed: {e}")

    # ============================================================
    # 错题库 / 诊断
    # ============================================================

    async def get_diagnosis(self, user_id: int, subject_id: str) -> dict:
        """获取错题库诊断统计"""
        if self._error_service:
            try:
                return await self._error_service.get_diagnosis(user_id, subject_id)
            except Exception as e:
                logger.warning(f"get_diagnosis failed: {e}")

        # Fallback mock
        return {
            "total_errors": 23,
            "weak_points": [
                {"kp_code": "math_func_composite", "kp_name": "复合函数", "mastery": 0.23, "error_count": 8},
                {"kp_code": "math_geometry_space", "kp_name": "空间向量", "mastery": 0.31, "error_count": 6},
                {"kp_code": "math_derivative_app", "kp_name": "导数应用", "mastery": 0.35, "error_count": 5},
                {"kp_code": "math_probability", "kp_name": "概率计算", "mastery": 0.45, "error_count": 4},
                {"kp_code": "math_func_monotone", "kp_name": "函数单调性", "mastery": 0.50, "error_count": 3},
            ],
            "exam_frequency": {
                "math_func_composite": 0.85,
                "math_geometry_space": 0.72,
                "math_derivative_app": 0.90,
                "math_probability": 0.78,
                "math_func_monotone": 0.65,
            },
        }

    async def get_prerequisite_kps(self, kp_code: str) -> list[dict]:
        """获取知识点的前置依赖知识点"""
        # 内建知识点 DAG（数学核心）
        PREREQ_MAP = {
            "math_func_composite": [{"code": "math_func_basic", "name": "基础函数"}],
            "math_geometry_space": [{"code": "math_geometry_plane", "name": "平面几何基础"}],
            "math_derivative_app": [{"code": "math_derivative", "name": "导数概念与运算"}],
            "math_derivative": [{"code": "math_func_limit", "name": "函数与极限"}],
            "math_probability": [{"code": "math_count", "name": "计数原理"}],
            "math_func_monotone": [{"code": "math_func_basic", "name": "基础函数"}],
        }
        return PREREQ_MAP.get(kp_code, [])

    # ============================================================
    # 题库
    # ============================================================

    async def recommend_questions(self, subject_id: str, kp_codes: list[str],
                                   theta: float, difficulty_min: float,
                                   difficulty_max: float, limit: int = 5,
                                   exclude_ids: list[int] | None = None) -> list[dict]:
        """基于IRT参数推荐题目"""
        if self._question_service:
            try:
                # 传给真实服务时带上difficulty参数（如不支持则被忽略）
                return await self._question_service.recommend_questions(
                    subject_id=subject_id, kp_codes=kp_codes,
                    theta=theta, limit=limit, exclude_ids=exclude_ids or [],
                    difficulty_min=difficulty_min, difficulty_max=difficulty_max,
                )
            except TypeError:
                # 真实服务可能不支持difficulty参数，降级调用
                return await self._question_service.recommend_questions(
                    subject_id=subject_id, kp_codes=kp_codes,
                    theta=theta, limit=limit, exclude_ids=exclude_ids or [],
                )
            except Exception as e:
                logger.warning(f"recommend_questions failed: {e}")

        # Fallback mock
        mock_qs = [
            {"id": 101, "content": "已知函数 f(x) = x³ - 3x² + 2，求 f(x) 的单调区间。", "kp_code": "math_func_monotone",
             "kp_name": "函数单调性", "irt_a": 1.2, "irt_b": 0.35, "score": 5, "q_type": "解答题", "source": "2024全国I卷·改编"},
            {"id": 102, "content": "求函数 y = 2^(x+1) 的定义域和值域。", "kp_code": "math_func_composite",
             "kp_name": "复合函数", "irt_a": 1.0, "irt_b": 0.25, "score": 5, "q_type": "选择题", "source": "2025黄冈模拟"},
            {"id": 103, "content": "空间四边形 ABCD 中，E,F,G,H 分别是 AB,BC,CD,DA 的中点，求证 EFGH 是平行四边形。",
             "kp_code": "math_geometry_space", "kp_name": "空间向量", "irt_a": 1.1, "irt_b": 0.45, "score": 8, "q_type": "解答题", "source": "人教版必修二"},
            {"id": 104, "content": "计算定积分 ∫₀¹ (x² - 2x + 1) dx", "kp_code": "math_derivative_app",
             "kp_name": "导数应用", "irt_a": 0.9, "irt_b": -0.1, "score": 5, "q_type": "填空题", "source": "2024全国II卷"},
            {"id": 105, "content": "从5名男生和3名女生中选3人，求至少1名女生的概率。", "kp_code": "math_probability",
             "kp_name": "概率计算", "irt_a": 0.8, "irt_b": 0.1, "score": 5, "q_type": "选择题", "source": "2023全国I卷"},
        ]
        return mock_qs[:limit]

    async def get_question_detail(self, question_id: int) -> Optional[dict]:
        """获取题目详情"""
        if self._question_service:
            try:
                return await self._question_service.get_question(question_id)
            except Exception as e:
                logger.warning(f"get_question_detail failed: {e}")
        return None

    # ============================================================
    # 组卷
    # ============================================================

    async def compose_exam(self, user_id: int, subject_id: str, theta: float,
                            question_count: int = 20,
                            focus_kps: list[str] | None = None,
                            assessment_mode: str = "cat") -> dict:
        """生成测评试卷"""
        if self._composition_service:
            try:
                return await self._composition_service.create_composition(
                    user_id=user_id, subject_id=subject_id,
                    question_count=question_count,
                )
            except Exception as e:
                logger.warning(f"compose_exam failed: {e}")

        # Fallback: 从 recommend_questions 拼凑
        questions = await self.recommend_questions(
            subject_id=subject_id,
            kp_codes=focus_kps or [],
            theta=theta, difficulty_min=theta - 0.5, difficulty_max=theta + 0.5,
            limit=min(question_count, 5),
        )
        return {
            "id": 1,
            "composition_id": 100,
            "questions": questions,
            "estimated_duration": 90,
        }


# 全局适配器实例（应用级单例）
_global_adapter: AgentServiceAdapter | None = None


def get_agent_adapter() -> AgentServiceAdapter:
    """获取全局适配器实例（延迟初始化）"""
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = AgentServiceAdapter()
    return _global_adapter
