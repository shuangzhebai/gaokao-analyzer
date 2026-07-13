"""F1: 学习诊断Agent — IRT确定性管道 + 可选LLM装饰"""
from __future__ import annotations
import logging

from .base import BaseAgent, AgentConfig
from .context import AgentContext

logger = logging.getLogger(__name__)


# Phase 1 系统提示（纯统计输出）
DIAGNOSIS_PHASE1_SYSTEM = """你是一位学习诊断助手。
你的职责是基于学生数据输出结构化诊断概要。

请确保输出的JSON包含：
{
  "summary": "诊断摘要（一句话）",
  "theta_estimate": 能力值,
  "overall_mastery": 总体掌握度0-1,
  "top_weak_points": [{"kp_code": "...", "kp_name": "...", "mastery": 0-1}],
  "strengths": [{"kp_code": "...", "kp_name": "..."}]
}
"""

# Phase 2 系统提示（LLM装饰）
DIAGNOSIS_PHASE2_SYSTEM = """你是一位资深高考学情分析师。
请基于数字诊断结果，为学生生成自然语言的归因分析和学习建议。

输出JSON格式：
{
  "weakness_root_cause": "薄弱点根因分析（≤100字）",
  "priority_advice": "优先级建议（≤80字）",
  "estimated_gain": "如果按计划复习，预计各科提分空间（字符串）",
  "study_strategy": "学习方法建议（≤80字）",
  "motivation_tip": "一句鼓励的话"
}
"""


class DiagnosisAgent:
    """学习诊断Agent — 两阶段混合设计"""

    def __init__(self, llm_client=None, adapter=None):
        self.llm_client = llm_client
        self._adapter = adapter
        self._agent = BaseAgent(
            AgentConfig(
                name="diagnosis",
                system_prompt=DIAGNOSIS_PHASE1_SYSTEM,
                tools=[],  # 0 FC tools — 确定性管道
            ),
            llm_client,
        ) if llm_client else None

    def set_adapter(self, adapter):
        """注入服务适配器"""
        self._adapter = adapter

    async def run_phase1(self, context: AgentContext,
                         student_service=None, error_service=None) -> AgentContext:
        """
        Phase 1：确定性计算管道，永远执行，不走LLM
        <500ms
        """
        try:
            # 使用适配器（优先传入的service，其次adapter）
            svc = self._adapter
            # 1. 获取学生IRT能力值
            profile = await (student_service or svc).get_profile(context.user_id, context.subject_id)
            theta = profile.get("theta", 0.0)
            knowledge_mastery = profile.get("knowledge_mastery", {})

            # 2. 获取错题统计
            error_stats = await (error_service or svc).get_diagnosis(context.user_id, context.subject_id)
            weak_points = error_stats.get("weak_points", [])

            # 3. 知识图谱根因分析（DAG追溯）
            if weak_points:
                root_causes = await self._trace_root_causes(
                    weak_points, knowledge_mastery, error_service
                )
            else:
                root_causes = []

            # 4. 构建结构化输出
            overall_mastery = sum(knowledge_mastery.values()) / len(knowledge_mastery) if knowledge_mastery else 0.5
            top_weak = sorted(weak_points, key=lambda x: x.get("mastery", 1))[:5] if weak_points else []
            strengths = sorted(
                [{"kp_code": k, "kp_name": k, "mastery": v}
                 for k, v in knowledge_mastery.items() if v >= 0.7],
                key=lambda x: -x["mastery"]
            )[:3]

            output = {
                "summary": f"当前{context.subject_id}能力theta={theta:.2f}，总体掌握度{overall_mastery:.0%}",
                "theta_estimate": theta,
                "overall_mastery": round(overall_mastery, 2),
                "top_weak_points": top_weak[:5],
                "root_causes": root_causes,
                "strengths": strengths,
                "phase": 1,
                "is_fallback": False,
            }
            context.set_output("diagnosis", output)
            context.student_profile = profile
            context.error_stats = error_stats
        except Exception as e:
            logger.exception("Phase1 diagnosis failed")
            context.set_output("diagnosis", {
                "error": str(e), "phase": 1, "is_fallback": True,
                "summary": "诊断计算异常，请稍后重试",
                "theta_estimate": 0.0, "overall_mastery": 0.5,
                "top_weak_points": [], "root_causes": [], "strengths": [],
            })
        return context

    async def run_phase2(self, context: AgentContext) -> AgentContext:
        """
        Phase 2：可选LLM装饰 — 用户点"查看详细报告"时才触发
        <8s，可模板降级
        """
        if not self.llm_client or not self._agent:
            diag_analysis = self._fallback_phase2(context)
            if context.diagnosis:
                context.diagnosis["llm_analysis"] = diag_analysis
                context.diagnosis["phase"] = 2
            return context

        diagnosis = context.diagnosis or {}
        if not diagnosis.get("top_weak_points"):
            diag_analysis = self._fallback_phase2(context)
            if context.diagnosis:
                context.diagnosis["llm_analysis"] = diag_analysis
                context.diagnosis["phase"] = 2
            return context

        try:
            phase2_messages = [
                {"role": "system", "content": DIAGNOSIS_PHASE2_SYSTEM},
                {"role": "user", "content":
                    f"学生theta={diagnosis.get('theta_estimate', 0):.2f}，"
                    f"薄弱点: {[w['kp_name'] for w in diagnosis.get('top_weak_points', [])[:3]]}。"
                    f"请给出归因分析和学习建议。"},
            ]
            # 直接调用LLM，不经过context.set_output（避免覆盖Phase1诊断结果）
            resp = await self.llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=phase2_messages,
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2048,
            )
            content = resp.choices[0].message.content or "{}"
            phase2_output = json.loads(content)
            diagnosis["llm_analysis"] = phase2_output
            diagnosis["phase"] = 2
            context.set_output("diagnosis", diagnosis)
        except Exception as e:
            logger.warning(f"Phase2 LLM failed, using fallback: {e}")
            diagnosis["llm_analysis"] = self._fallback_phase2(context)
            diagnosis["phase"] = 2
            context.set_output("diagnosis", diagnosis)
        return context

    def _fallback_phase2(self, context: AgentContext) -> dict:
        """Phase2 LLM不可用时降级"""
        return {
            "weakness_root_cause": "薄弱知识点存在关联性，建议从掌握度最低的基础知识点开始逐个突破。",
            "priority_advice": "优先复习掌握度低于0.4的知识点，这些是提升最快的区域。",
            "estimated_gain": "按计划系统复习，预计可提升15-25分",
            "study_strategy": "每天2小时系统学习（1小时新知识+30分钟复习+30分钟练习）",
            "motivation_tip": "每一个薄弱点都是一块垫脚石，跨过去就会更高一点！",
            "is_fallback": True,
        }

    async def _trace_root_causes(self, weak_points: list, knowledge_mastery: dict,
                                  error_service=None) -> list:
        """DAG追溯薄弱点的根因知识点"""
        svc = self._adapter or error_service
        root_causes = []
        for wp in weak_points[:5]:
            prereqs = await svc.get_prerequisite_kps(wp.get("kp_code", ""))
            if prereqs:
                for p in prereqs:
                    p_mastery = knowledge_mastery.get(p.get("code", ""), 0.5)
                    if p_mastery < 0.5:
                        root_causes.append({
                            "kp_code": wp.get("kp_code"),
                            "kp_name": wp.get("kp_name"),
                            "root_cause_code": p.get("code"),
                            "root_cause_name": p.get("name"),
                            "root_cause_mastery": p_mastery,
                        })
                        break
        return root_causes
