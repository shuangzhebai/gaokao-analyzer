"""Agent间共享内存池 — 请求级生命周期"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import uuid


@dataclass
class AgentContext:
    """Agent间共享内存池 — 请求级生命周期，asyncio安全"""

    # === 输入 ===
    user_id: int
    subject_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trigger: str = "manual"  # manual | scheduled | after_error

    # === Agent输出（各Agent写入） ===
    diagnosis: dict | None = None
    learning_plan: dict | None = None
    recommendations: list | None = None
    assessment: dict | None = None
    explanation: dict | None = None       # F7: 结构化讲解输出

    # === 共享状态 ===
    history: list[dict] = field(default_factory=list)
    current_agent: str = ""
    errors: list[str] = field(default_factory=list)
    tool_call_log: list[dict] = field(default_factory=list)

    # === LLM成本追踪 ===
    last_llm_cost: dict | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # === 缓存引用（避免重复查询） ===
    student_profile: dict | None = None
    error_stats: dict | None = None
    knowledge_tree: dict | None = None
    focus_kps: list[str] | None = None    # 可选，聚焦知识点

    def set_output(self, agent_name: str, output: dict) -> None:
        self.current_agent = agent_name
        if agent_name == "diagnosis":
            self.diagnosis = output
        elif agent_name == "planning":
            self.learning_plan = output
        elif agent_name == "recommendation":
            self.recommendations = output if isinstance(output, list) else output.get("questions", output)
        elif agent_name == "assessment":
            self.assessment = output
        elif agent_name == "explain":
            self.explanation = output
        if self.last_llm_cost:
            self.total_prompt_tokens += self.last_llm_cost.get("prompt_tokens", 0)
            self.total_completion_tokens += self.last_llm_cost.get("completion_tokens", 0)
        self.history.append({
            "role": "assistant",
            "agent": agent_name,
            "output": output,
        })

    def add_tool_call(self, record: dict) -> None:
        self.tool_call_log.append(record)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.history.append({"role": "system", "error": msg})

    def to_dict(self) -> dict:
        """序列化用于API响应"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "subject_id": self.subject_id,
            "trigger": self.trigger,
            "current_agent": self.current_agent,
            "diagnosis": self.diagnosis,
            "learning_plan": self.learning_plan,
            "recommendations": self.recommendations,
            "assessment": self.assessment,
            "explanation": self.explanation,
            "errors": self.errors,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
        }
