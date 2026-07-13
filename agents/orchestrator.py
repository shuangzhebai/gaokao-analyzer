"""Agent编排器 — asyncio State Machine"""
from __future__ import annotations
from enum import StrEnum
from typing import Callable
import logging
import asyncio

from .context import AgentContext
from .base import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorState(StrEnum):
    IDLE = "idle"
    DIAGNOSING = "diagnosing"
    DIAGNOSIS_DONE = "diagnosis_done"
    PLANNING = "planning"
    PLANNING_DONE = "planning_done"
    RECOMMENDING = "recommending"
    RECOMMENDING_DONE = "recommending_done"
    ASSESSING = "assessing"
    ASSESSING_DONE = "assessing_done"
    FEEDBACK = "feedback"
    COMPLETED = "completed"
    FAILED = "failed"


# 状态转移表
TRANSITIONS: dict[OrchestratorState, list[OrchestratorState]] = {
    OrchestratorState.IDLE: [OrchestratorState.DIAGNOSING],
    OrchestratorState.DIAGNOSING: [OrchestratorState.DIAGNOSIS_DONE, OrchestratorState.FAILED],
    OrchestratorState.DIAGNOSIS_DONE: [OrchestratorState.PLANNING],
    OrchestratorState.PLANNING: [OrchestratorState.PLANNING_DONE, OrchestratorState.FAILED],
    OrchestratorState.PLANNING_DONE: [OrchestratorState.RECOMMENDING],
    OrchestratorState.RECOMMENDING: [OrchestratorState.RECOMMENDING_DONE, OrchestratorState.FAILED],
    OrchestratorState.RECOMMENDING_DONE: [OrchestratorState.ASSESSING],
    OrchestratorState.ASSESSING: [OrchestratorState.ASSESSING_DONE, OrchestratorState.FAILED],
    OrchestratorState.ASSESSING_DONE: [OrchestratorState.FEEDBACK, OrchestratorState.COMPLETED],
    OrchestratorState.FEEDBACK: [OrchestratorState.DIAGNOSING],
}


class AgentOrchestrator:
    """Agent编排器 — 管理状态转换与Agent调度"""

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}
        self._state_handlers: dict[OrchestratorState, Callable] = {}

    def register(self, name: str, agent: BaseAgent) -> None:
        self._agents[name] = agent

    def get_agent(self, name: str) -> BaseAgent | None:
        """公开获取注册的Agent实例"""
        return self._agents.get(name)

    def on_state(self, state: OrchestratorState, handler: Callable) -> None:
        self._state_handlers[state] = handler

    async def run_full_cycle(self, context: AgentContext) -> AgentContext:
        """运行完整闭环：诊断→规划→推荐→测评→反馈"""
        state = OrchestratorState.DIAGNOSING
        max_loops = 20  # 防止无限循环

        for loop_idx in range(max_loops):
            handler = self._state_handlers.get(state)
            if not handler:
                if state == OrchestratorState.COMPLETED:
                    return context
                context.add_error(f"No handler for state: {state}")
                return context

            try:
                next_state = await handler(context)
            except Exception as e:
                logger.exception(f"State {state} handler failed: {e}")
                context.add_error(f"State {state} failed: {e}")
                return context

            # 验证状态转移合法性
            allowed = TRANSITIONS.get(state, [])
            if next_state not in allowed:
                logger.warning(f"Illegal transition: {state} → {next_state}, allowed: {allowed}")
                context.add_error(f"Illegal transition: {state} → {next_state}")
                return context

            state = next_state

        context.add_error("Max loops exceeded")
        return context

    async def run_single(self, agent_name: str, context: AgentContext) -> AgentContext:
        """运行单个Agent"""
        agent = self._agents.get(agent_name)
        if not agent:
            context.add_error(f"Unknown agent: {agent_name}")
            return context
        return await agent.run(context)
