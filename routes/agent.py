"""Agent 编排 API 路由 — v7.0 新增"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio
import logging
import openai

from ..deps import get_current_user
from ..agents.orchestrator import AgentOrchestrator, OrchestratorState
from ..agents.context import AgentContext
from ..agents.diagnosis_agent import DiagnosisAgent
from ..agents.planning_agent import PlanningAgent
from ..agents.recommendation_agent import RecommendationAgent
from ..agents.assessment_agent import AssessmentAgent
from ..services.agent_service_adapter import get_agent_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent编排"])


class AgentRunRequest(BaseModel):
    subject_id: str
    trigger: str = "manual"
    focus_kps: Optional[list[str]] = None


class ExplainRequest(BaseModel):
    kp_code: str
    kp_name: str
    mastery: float
    theta: float
    subject_id: str
    use_llm: bool = True


# 共享编排器实例（应用级单例，asyncio.Lock 保证线程安全）
_orchestrator: AgentOrchestrator | None = None
_orchestrator_lock = asyncio.Lock()


async def get_orchestrator() -> AgentOrchestrator:
    """获取编排器实例（延迟初始化，线程安全）。"""
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    async with _orchestrator_lock:
        if _orchestrator is not None:  # Double-check
            return _orchestrator

        adapter = get_agent_adapter()
        client = openai.AsyncOpenAI()
        _orchestrator = AgentOrchestrator()

        diag_agent = DiagnosisAgent(client, adapter=adapter)
        _orchestrator.register("diagnosis", diag_agent)
        _orchestrator.register("planning", PlanningAgent(client))
        _orchestrator.register("recommendation", RecommendationAgent(client))
        _orchestrator.register("assessment", AssessmentAgent(adapter=adapter))

        async def handle_diagnosing(ctx: AgentContext):
            diag_agent = _orchestrator.get_agent("diagnosis")
            if diag_agent:
                await diag_agent.run_phase1(ctx, adapter, adapter)
            return OrchestratorState.DIAGNOSIS_DONE

        async def handle_planning(ctx: AgentContext):
            agent = _orchestrator.get_agent("planning")
            if agent:
                await agent.run(ctx, adapter)
            return OrchestratorState.PLANNING_DONE

        async def handle_recommending(ctx: AgentContext):
            agent = _orchestrator.get_agent("recommendation")
            if agent:
                await agent.run(ctx, adapter)
            return OrchestratorState.RECOMMENDING_DONE

        async def handle_assessing(ctx: AgentContext):
            agent = _orchestrator.get_agent("assessment")
            if agent:
                diag = ctx.diagnosis or {}
                await agent.generate_assessment(
                    ctx, user_id=ctx.user_id, subject_id=ctx.subject_id,
                    theta=diag.get("theta_estimate", 0.0),
                    question_count=20,
                )
            return OrchestratorState.ASSESSING_DONE

        _orchestrator.on_state(OrchestratorState.DIAGNOSING, handle_diagnosing)
        _orchestrator.on_state(OrchestratorState.DIAGNOSIS_DONE, lambda ctx: OrchestratorState.PLANNING)
        _orchestrator.on_state(OrchestratorState.PLANNING, handle_planning)
        _orchestrator.on_state(OrchestratorState.PLANNING_DONE, lambda ctx: OrchestratorState.RECOMMENDING)
        _orchestrator.on_state(OrchestratorState.RECOMMENDING, handle_recommending)
        _orchestrator.on_state(OrchestratorState.RECOMMENDING_DONE, lambda ctx: OrchestratorState.ASSESSING)
        _orchestrator.on_state(OrchestratorState.ASSESSING, handle_assessing)
        _orchestrator.on_state(OrchestratorState.ASSESSING_DONE, lambda ctx: OrchestratorState.COMPLETED)

        return _orchestrator


@router.post("/run")
async def run_agent_cycle(
    req: AgentRunRequest,
    user: dict = Depends(get_current_user),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """启动完整Agent闭环：诊断→规划→推荐→测评"""
    context = AgentContext(
        user_id=user["id"],
        subject_id=req.subject_id,
        trigger=req.trigger,
        focus_kps=req.focus_kps,
    )
    result = await orchestrator.run_full_cycle(context)
    return {"status": "ok", "data": result.to_dict()}


@router.post("/run/{agent_name}")
async def run_single_agent(
    agent_name: str,
    req: AgentRunRequest,
    user: dict = Depends(get_current_user),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    """单独运行指定Agent"""
    valid_agents = {"diagnosis", "planning", "recommendation", "assessment"}
    if agent_name not in valid_agents:
        raise HTTPException(status_code=400, detail=f"Invalid agent: {agent_name}")

    context = AgentContext(
        user_id=user["id"],
        subject_id=req.subject_id,
    )
    if agent_name == "diagnosis":
        adapter = get_agent_adapter()
        diag_agent = orchestrator.get_agent("diagnosis")
        if diag_agent:
            await diag_agent.run_phase1(context, adapter, adapter)
    else:
        result = await orchestrator.run_single(agent_name, context)
    return {"status": "ok", "agent": agent_name, "data": context.to_dict()}


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """查询闭环会话状态与结果"""
    return {"session_id": session_id, "status": "not_found"}


@router.get("/session/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE流式订阅Agent执行过程"""

    async def event_stream():
        try:
            yield f"data: {json.dumps({'event': 'connected', 'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'event': 'complete'})}\n\n"
        except asyncio.CancelledError:
            logger.info(f"SSE stream {session_id} disconnected")
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history")
async def get_agent_history(user: dict = Depends(get_current_user)):
    """用户历史Agent会话列表"""
    return {"status": "ok", "data": []}


@router.post("/explain")
async def get_explain(
    req: ExplainRequest,
    user: dict = Depends(get_current_user),
):
    """F7: 知识结构化讲解"""
    from ..agents.recommendation_agent import RecommendationAgent
    from ..services.agent_service_adapter import get_agent_adapter

    client = _get_openai_client()
    adapter = get_agent_adapter()
    agent = RecommendationAgent(client)
    ctx = AgentContext(user_id=user["id"], subject_id=req.subject_id)

    await agent.run_explain(
        ctx,
        kp_code=req.kp_code,
        kp_name=req.kp_name,
        mastery=req.mastery,
        theta=req.theta,
        subject_id=req.subject_id,
        llm_client=client,
        use_llm=req.use_llm,
    )
    return {"status": "ok", "data": ctx.explanation}
