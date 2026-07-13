"""Agent 基类 — 封装LLM调用+Function Calling循环"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from openai import AsyncOpenAI, APIError, RateLimitError
import time
import json
import logging
import asyncio

from .context import AgentContext

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    tools: list[dict] = field(default_factory=list)
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 4096
    max_retries: int = 2
    timeout: float = 30.0


class BaseAgent:
    """Agent基类 — 封装LLM调用+Function Calling循环"""

    def __init__(self, config: AgentConfig, client: AsyncOpenAI):
        self.config = config
        self.client = client

    async def run(self, context: AgentContext) -> AgentContext:
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            *context.history,
        ]
        if not self.config.tools:
            return await self._simple_call(messages, context)
        return await self._fc_loop(messages, context)

    async def _simple_call(self, messages: list, context: AgentContext) -> AgentContext:
        """单次LLM调用（非FC模式）。记录token成本。"""
        start = time.monotonic()
        for attempt in range(self.config.max_retries + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"},
                    timeout=self.config.timeout,
                )
                content = resp.choices[0].message.content or "{}"
                usage = resp.usage
                cost = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "latency_ms": int((time.monotonic() - start) * 1000),
                }
                context.last_llm_cost = cost
                context.total_prompt_tokens += cost["prompt_tokens"]
                context.total_completion_tokens += cost["completion_tokens"]
                context.set_output(self.config.name, json.loads(content))
                return context
            except (APIError, RateLimitError, json.JSONDecodeError) as e:
                logger.warning(f"[{self.config.name}] LLM call attempt {attempt+1} failed: {e}")
                if attempt < self.config.max_retries:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                context.set_output(self.config.name, {"error": str(e), "fallback": True})
                return context

    async def _fc_loop(self, messages: list, context: AgentContext) -> AgentContext:
        """多轮Function Calling循环，记录token成本。"""
        max_rounds = 10
        start = time.monotonic()

        # 工具查找表 — 过滤掉没有handler的工具
        tool_map: dict[str, Callable] = {}
        clean_tools: list[dict] = []
        for t in self.config.tools:
            name = t.get("function", {}).get("name")
            handler = t.get("handler")
            if name and handler:
                tool_map[name] = handler
                clean_tools.append({k: v for k, v in t.items() if k != "handler"})

        for round_idx in range(max_rounds):
            resp = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                tools=clean_tools,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
            )
            msg = resp.choices[0].message
            usage = resp.usage
            if usage:
                context.total_prompt_tokens += usage.prompt_tokens or 0
                context.total_completion_tokens += usage.completion_tokens or 0

            if not msg.tool_calls:
                content = msg.content or "{}"
                try:
                    context.set_output(self.config.name, json.loads(content))
                except json.JSONDecodeError:
                    context.set_output(self.config.name, {"text": content})
                context.last_llm_cost = {
                    "latency_ms": int((time.monotonic() - start) * 1000),
                }
                return context

            # 执行工具调用
            for tc in msg.tool_calls:
                func_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                handler = tool_map.get(func_name)
                if handler:
                    try:
                        result = await handler(context, **args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                    except Exception as e:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": str(e)}),
                        })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": f"Unknown tool: {func_name}"}),
                    })

            context.add_tool_call({
                "round": round_idx,
                "tool_calls": [{"name": tc.function.name, "args": tc.function.arguments}
                               for tc in msg.tool_calls],
            })

        context.set_output(self.config.name, {"error": "max_rounds_exceeded"})
        return context
