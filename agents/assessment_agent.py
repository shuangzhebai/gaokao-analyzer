"""F4: 阶段测评Agent — CAT自适应+CP-SAT组卷+闭环反馈"""
from __future__ import annotations
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AssessmentAgent:
    """阶段测评Agent — 调用CP-SAT组卷引擎 + IRT能力估计"""

    def __init__(self, composition_service=None, question_service=None, adapter=None):
        self.composition_service = composition_service
        self.question_service = question_service
        self._adapter = adapter

    async def generate_assessment(self, context, user_id: int, subject_id: str,
                                   theta: float, focus_kps: list[str] | None = None,
                                   question_count: int = 20) -> AgentContext:
        """
        生成自适应阶段测评卷
        - 复用现有OR-Tools CP-SAT组卷引擎
        - 自适应选题：第1题匹配theta，后续动态调整
        - 返回测评卷信息
        """
        if not self.composition_service:
            # 有adapter时生成Mock测评卷
            if self._adapter:
                try:
                    composition = await self._adapter.compose_exam(
                        user_id=user_id, subject_id=subject_id,
                        theta=theta, question_count=question_count, focus_kps=focus_kps,
                    )
                    context.set_output("assessment", {
                        "assessment_id": composition.get("id"),
                        "composition_id": composition.get("composition_id"),
                        "questions": composition.get("questions", []),
                        "total_questions": question_count,
                        "estimated_duration_minutes": composition.get("estimated_duration", 90),
                        "theta_at_generation": theta,
                        "status": "generated",
                        "is_fallback": True,
                    })
                    return context
                except Exception as e:
                    logger.warning(f"Adapter compose_exam failed: {e}")
            context.set_output("assessment", {
                "error": "composition_service not available",
                "is_fallback": True,
            })
            return context

        try:
            # 调用组卷引擎生成测评卷
            composition = await self.composition_service.compose_exam(
                user_id=user_id,
                subject_id=subject_id,
                theta=theta,
                question_count=question_count,
                focus_kps=focus_kps,
                assessment_mode="cat",  # CAT自适应模式
            )
            context.set_output("assessment", {
                "assessment_id": composition.get("id"),
                "composition_id": composition.get("composition_id"),
                "questions": composition.get("questions", []),
                "total_questions": question_count,
                "estimated_duration_minutes": composition.get("estimated_duration", 90),
                "theta_at_generation": theta,
                "status": "generated",
                "is_fallback": False,
            })
        except Exception as e:
            logger.exception("Assessment generation failed")
            context.set_output("assessment", {
                "error": str(e),
                "is_fallback": True,
                "status": "failed",
            })
        return context

    async def submit_and_evaluate(self, context, assessment_id: int,
                                   answers: list[dict] | None = None,
                                   question_service=None,
                                   analysis_service=None) -> AgentContext:
        """
        提交测评答案并评估：
        1. 评分
        2. 更新IRT theta值
        3. 更新知识图谱掌握度
        4. 生成反馈报告
        """
        # 处理空/None输入
        if not answers:
            context.add_error("submit_and_evaluate: no answers provided")
            report = self._empty_report(assessment_id)
            context.set_output("assessment", {
                **(context.assessment or {}),
                "status": "completed", "report": report, "is_fallback": True,
            })
            return context

        # 评分
        correct_count = sum(1 for a in answers if a.get("correct", False))
        total = len(answers) or 1
        score = correct_count / total

        # 更新IRT（简化版 - 实际用3PL模型更新）
        old_theta = context.assessment.get("theta_at_generation", 0) if context.assessment else 0
        new_theta = old_theta + (score - 0.5) * 0.3  # 简化更新公式
        new_theta = max(-3, min(3, new_theta))

        # 生成反馈报告
        report = {
            "assessment_id": assessment_id,
            "score": round(score * 100, 1),
            "total_score": 100,
            "correct_count": correct_count,
            "total_count": total,
            "theta_before": old_theta,
            "theta_after": round(new_theta, 2),
            "theta_shift": round(new_theta - old_theta, 2),
            "weakness_resolved": [],
            "new_weaknesses": [],
            "recommendations": [],
            "generated_at": datetime.now().isoformat(),
        }

        # 分析各知识点掌握度变化
        if question_service:
            for a in answers:
                q_detail = await question_service.get_question_detail(a.get("question_id"))
                if q_detail:
                    kp = q_detail.get("kp_code", "")
                    if a.get("correct", False):
                        report["weakness_resolved"].append(kp)
                    else:
                        report["new_weaknesses"].append(kp)

        context.set_output("assessment", {
            **(context.assessment or {}),
            "status": "completed",
            "report": report,
            "is_fallback": False,
        })
        return context

    def _empty_report(self, assessment_id: int) -> dict:
        """生成空测评报告（降级/兜底用）"""
        return {
            "assessment_id": assessment_id,
            "score": 0, "total_score": 100,
            "correct_count": 0, "total_count": 0,
            "theta_before": 0, "theta_after": 0, "theta_shift": 0,
            "weakness_resolved": [], "new_weaknesses": [],
            "recommendations": [],
            "generated_at": datetime.now().isoformat(),
            "is_fallback": True,
        }

    async def feedback_to_diagnosis(self, context, student_service=None) -> AgentContext:
        """
        反馈闭环：测评结果 → 更新IRT模型 → 存入student_profiles
        """
        if not student_service:
            logger.warning("feedback_to_diagnosis: no student_service provided")
            return context

        report = (context.assessment or {}).get("report", {})
        if not report:
            return context

        try:
            await student_service.update_profile(
                user_id=context.user_id,
                subject_id=context.subject_id,
                theta=report.get("theta_after"),
                new_weaknesses=report.get("new_weaknesses", []),
                resolved_weaknesses=report.get("weakness_resolved", []),
            )
        except Exception as e:
            logger.warning(f"Feedback update failed: {e}")
        return context
