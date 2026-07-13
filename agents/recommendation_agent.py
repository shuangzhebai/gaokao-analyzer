"""F3: 习题推荐Agent + F7: 结构化讲解 — speed-first设计"""
from __future__ import annotations
import logging
import json

from .base import BaseAgent, AgentConfig
from .tools.explain_tools import build_explain_payload, build_fallback_explain

logger = logging.getLogger(__name__)

RECOMMEND_SYSTEM = """你是一位精准出题师。基于学生诊断结果，推荐最合适的练习题。

输出JSON格式：
{
  "mode": "recommend",
  "focus_kp_codes": ["推荐的知识点代码列表，最多3个"],
  "difficulty_range": {"min_b": 最小b值, "max_b": 最大b值},
  "count": 推荐题目数,
  "exclude_question_ids": ["已做过的题目ID，避免重复推荐"],
  "variation_count": 变式题数量
}

## 推荐约束
- 每道题IRT难度b值在[student_theta-0.3, student_theta+0.5]区间
- 优先推荐目标知识点（掌握度<0.6）
- 题型多样性（不连续推荐同一子类型）
- 推荐数3-5道
"""


class RecommendationAgent:
    """习题推荐Agent — 单次LLM JSON Output → SQL批量查询"""

    def __init__(self, llm_client):
        self._agent = BaseAgent(
            AgentConfig(
                name="recommendation",
                system_prompt=RECOMMEND_SYSTEM,
                tools=[],  # 0 FC tools — 单次LLM+SQL
                temperature=0.2,
            ),
            llm_client,
        )

    async def run(self, context, adapter=None) -> AgentContext:
        """执行推荐 — 使用adapter或context数据"""
        diag = context.diagnosis or {}
        weak_top5 = diag.get("top_weak_points", [])[:3]
        theta = diag.get("theta_estimate", 0.0)

        # 构建LLM输入
        weak_kps = [{"code": w.get("kp_code", ""), "name": w.get("kp_name", ""),
                      "mastery": w.get("mastery", 0.5)} for w in weak_top5]

        context.history.append({
            "role": "user",
            "content": json.dumps({
                "theta": theta,
                "subject": context.subject_id,
                "weak_points": weak_kps,
            }, ensure_ascii=False),
        })

        # Step 1: LLM决定推荐参数
        llm_messages = [{"role": "system", "content": RECOMMEND_SYSTEM}] + context.history[-1:]
        plan = {}
        if self._agent and self._agent.client:
            try:
                # 直接调用LLM，不经过context.set_output
                resp = await self._agent.client.chat.completions.create(
                    model=self._agent.config.model,
                    messages=llm_messages,
                    response_format={"type": "json_object"},
                    temperature=self._agent.config.temperature,
                    max_tokens=self._agent.config.max_tokens,
                )
                content = resp.choices[0].message.content or "{}"
                plan = json.loads(content)
            except Exception as e:
                logger.warning(f"Recommend LLM failed: {e}")

        focus_kps = plan.get("focus_kp_codes", [k["code"] for k in weak_kps])
        difficulty = plan.get("difficulty_range", {"min_b": max(0, theta - 0.3), "max_b": theta + 0.5})
        count = min(plan.get("count", 5), 5)
        exclude_ids = plan.get("exclude_question_ids", [])

        # Step 2: 从适配器获取题目
        questions = []
        svc = adapter
        if svc:
            questions = await svc.recommend_questions(
                subject_id=context.subject_id,
                kp_codes=focus_kps,
                theta=theta,
                difficulty_min=difficulty.get("min_b", theta - 0.3),
                difficulty_max=difficulty.get("max_b", theta + 0.5),
                limit=count,
                exclude_ids=exclude_ids,
            )

        # Step 3: 后处理排序 + 添加推荐理由
        result_list = []
        for q in questions:
            kp_name = q.get("kp_name", "")
            mastery = 0.5
            for wp in weak_top5:
                if wp.get("kp_name") == kp_name or wp.get("kp_code") == q.get("kp_code"):
                    mastery = wp.get("mastery", 0.5)
                    break
            result_list.append({
                "question_id": q.get("id"),
                "preview": q.get("content", "")[:100],
                "target_kp": kp_name,
                "target_kp_code": q.get("kp_code"),
                "difficulty": "简单" if q.get("irt_b", 0) < -0.5 else "中等" if q.get("irt_b", 0) < 0.5 else "困难",
                "difficulty_match": f"略高于当前水平" if q.get("irt_b", 0) > theta else "符合当前水平",
                "estimated_time": f"{max(3, q.get('score', 5) // 2)}分钟",
                "reason": f"你在「{kp_name}」掌握度仅{mastery:.0%}，该考点需重点练习",
                "mastery_before": mastery,
                "source": q.get("source", "题库"),
                "question_type": q.get("q_type", "选择题"),
                "irt_a": q.get("irt_a"),
                "irt_b": q.get("irt_b"),
            })

        context.set_output("recommendation", result_list)
        return context

    async def run_explain(self, context, kp_code: str, kp_name: str,
                           mastery: float, theta: float, subject_id: str,
                           llm_client=None, use_llm: bool = True) -> AgentContext:
        """
        F7: 知识结构化讲解
        mastery<0.4时触发，<8s，可模板降级
        """
        exam_freq = 0.5  # 可从数据库查询
        question_count = 0

        if use_llm and llm_client:
            payload = build_explain_payload(
                context, kp_code, kp_name, mastery, theta,
                subject_id, exam_freq, question_count,
            )
            try:
                messages = [
                    {"role": "system", "content": payload["system_prompt"]},
                    {"role": "user", "content": payload["user_message"]},
                ]
                resp = await llm_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    response_format=payload["response_format"],
                    temperature=0.3,
                    max_tokens=2048,
                )
                content = resp.choices[0].message.content or "{}"
                explanation = json.loads(content)
                explanation["is_fallback"] = False
            except Exception as e:
                logger.warning(f"Explain LLM failed: {e}, using fallback")
                explanation = build_fallback_explain(subject_id, kp_name, mastery)
        else:
            explanation = build_fallback_explain(subject_id, kp_name, mastery)

        context.set_output("explain", explanation)
        return context
