"""F2: 课程规划Agent — 约束优化+ZPD路径规划"""
from __future__ import annotations
import logging

from .base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)

PLANNING_SYSTEM_PROMPT = """你是一位高考备考规划师。根据学生诊断结果生成个性化学习路径。

输出严格的JSON格式：
{
  "goal": "一句话学习目标",
  "estimated_hours": 总预计学习小时数,
  "phases": [
    {
      "name": "阶段名称（如：基础补漏期）",
      "duration_days": 阶段天数,
      "description": "阶段说明（≤50字）",
      "milestones": [
        {
          "kp_code": "知识点代码",
          "kp_name": "知识点名称",
          "target_mastery": 目标准确率0-1,
          "mastery_from": 当前掌握度,
          "estimated_questions": 预计练习数量,
          "textbook_chapter": "对应教材章节"
        }
      ],
      "weekly_plan": {
        "周一": [{"time_slot": "40min", "action": "具体任务描述", "kp_code": "..."}],
        ...
      },
      "checkpoint": "阶段检查点描述"
    }
  ],
  "estimated_completion": "预计完成日期"
}

## 规划约束
- 每天可用学习时间上限: {daily_hours}h
- 距离考试: {days_to_exam}天
- 前置知识约束：某个知识点未掌握前不要推荐其后续知识点
- 学科交叉：不连续两天只学同一科
- ZPD区间：推荐掌握度在0.2-0.7之间的知识点（太高的巩固就好，太低的先补前置知识）
"""


class PlanningAgent:
    """课程规划Agent — FC驱动，2-3轮Function Calling循环"""

    def __init__(self, llm_client):
        self._agent = BaseAgent(
            AgentConfig(
                name="planning",
                system_prompt=PLANNING_SYSTEM_PROMPT,
                tools=self._build_tools(),
                temperature=0.4,
            ),
            llm_client,
        )

    def _build_tools(self) -> list[dict]:
        """注册FC工具 — 规划Agent需要查询知识图谱和教材映射"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_knowledge_prerequisites",
                    "description": "获取某个知识点的前置知识点列表（DAG依赖）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kp_codes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "知识点代码列表",
                            },
                        },
                        "required": ["kp_codes"],
                        "additionalProperties": False,
                    },
                },
                "handler": self._handle_get_prerequisites,
            },
            {
                "type": "function",
                "function": {
                    "name": "get_textbook_chapters",
                    "description": "获取知识点对应的教材章节信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kp_code": {"type": "string", "description": "知识点代码"},
                        },
                        "required": ["kp_code"],
                        "additionalProperties": False,
                    },
                },
                "handler": self._handle_get_textbook,
            },
            {
                "type": "function",
                "function": {
                    "name": "get_exam_frequency_rank",
                    "description": "获取知识点的考频排名",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "kp_codes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "知识点代码列表",
                            },
                        },
                        "required": ["kp_codes"],
                        "additionalProperties": False,
                    },
                },
                "handler": self._handle_get_frequency,
            },
        ]

    async def run(self, context, textbook_service=None):
        """生成学习路径"""
        diag = context.diagnosis or {}
        weak_top5 = diag.get("top_weak_points", [])[:5]
        theta = diag.get("theta_estimate", 0.0)

        # 构建规划上下文
        weak_points_str = "; ".join([
            f"{w.get('kp_name', '?')}(掌握度{w.get('mastery', 0):.0%})"
            for w in weak_top5
        ])

        daily_hours = 2  # 默认每天2小时
        days_to_exam = 312  # 默认距离高考312天

        system_prompt = PLANNING_SYSTEM_PROMPT.format(
            daily_hours=daily_hours, days_to_exam=days_to_exam,
        )

        context.history.append({
            "role": "user",
            "content": f"学生{context.subject_id}诊断结果：theta={theta:.2f}，"
                       f"薄弱知识点TOP5：{weak_points_str}。"
                       f"请生成一份学习路径规划。",
        })

        return await self._agent._fc_loop(
            [{"role": "system", "content": system_prompt}] + context.history[-1:],
            context,
        )

    async def _handle_get_prerequisites(self, context, kp_codes: list[str]) -> list[dict]:
        """FC工具：查询前置知识点"""
        from ..services.agents.prerequisite_service import get_prerequisites
        return await get_prerequisites(context, kp_codes)

    async def _handle_get_textbook(self, context, kp_code: str) -> dict:
        """FC工具：查询教材章节"""
        from ..services.agents.textbook_service import get_chapter_for_kp
        return await get_chapter_for_kp(context, kp_code)

    async def _handle_get_frequency(self, context, kp_codes: list[str]) -> list[dict]:
        """FC工具：查询考频排名"""
        from ..services.agents.frequency_service import get_exam_frequency
        return await get_exam_frequency(context, kp_codes)
