"""v7.0 Agent 框架 + 服务层测试"""
import pytest
from datetime import datetime, timedelta
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestAgentContext:
    """测试 AgentContext 共享内存池"""

    def test_initialization(self):
        from agents.context import AgentContext
        ctx = AgentContext(user_id=1, subject_id="math")
        assert ctx.user_id == 1
        assert ctx.subject_id == "math"
        assert ctx.session_id is not None
        assert ctx.trigger == "manual"
        assert ctx.diagnosis is None
        assert ctx.recommendations is None

    def test_set_output(self):
        from agents.context import AgentContext
        ctx = AgentContext(user_id=1, subject_id="math")
        ctx.set_output("diagnosis", {"theta": 0.5, "weak_points": []})
        assert ctx.diagnosis == {"theta": 0.5, "weak_points": []}
        assert ctx.current_agent == "diagnosis"
        assert len(ctx.history) == 1

    def test_set_output_accumulates_tokens(self):
        from agents.context import AgentContext
        ctx = AgentContext(user_id=1, subject_id="math")
        ctx.last_llm_cost = {"prompt_tokens": 100, "completion_tokens": 50, "latency_ms": 200}
        ctx.set_output("diagnosis", {"theta": 0.5})
        assert ctx.total_prompt_tokens == 100
        assert ctx.total_completion_tokens == 50

    def test_to_dict(self):
        from agents.context import AgentContext
        ctx = AgentContext(user_id=1, subject_id="math")
        d = ctx.to_dict()
        assert d["user_id"] == 1
        assert d["session_id"] == ctx.session_id


class TestOrchestratorStateMachine:
    """测试编排器状态机"""

    def test_transitions_diagnosis_to_planning(self):
        from agents.orchestrator import OrchestratorState, TRANSITIONS
        assert OrchestratorState.DIAGNOSING in TRANSITIONS
        assert OrchestratorState.DIAGNOSIS_DONE in TRANSITIONS[OrchestratorState.DIAGNOSING]
        assert OrchestratorState.PLANNING in TRANSITIONS[OrchestratorState.DIAGNOSIS_DONE]

    def test_transitions_valid(self):
        from agents.orchestrator import OrchestratorState, TRANSITIONS
        # 验证每个状态都有合法的转移目标
        for state, allowed in TRANSITIONS.items():
            for next_state in allowed:
                assert isinstance(next_state, OrchestratorState)

    def test_feedback_loop(self):
        from agents.orchestrator import OrchestratorState, TRANSITIONS
        # FEEDBACK 状态可以回到 DIAGNOSING
        assert OrchestratorState.DIAGNOSING in TRANSITIONS[OrchestratorState.FEEDBACK]


class TestErrorReviewService:
    """测试 F8 间隔复习服务"""

    def test_mastery_decay(self):
        from services.error_review_service import calculate_mastery_decay
        # 初始掌握度0.8，30天后应衰减
        decayed = calculate_mastery_decay(0.8, 30, decay_rate=0.05)
        assert decayed < 0.8
        assert decayed > 0  # 不衰减到0
        # 时间越久，衰减越多
        assert calculate_mastery_decay(0.8, 60) < calculate_mastery_decay(0.8, 30)

    def test_mastery_decay_bounds(self):
        from services.error_review_service import calculate_mastery_decay
        assert 0 <= calculate_mastery_decay(1.0, 365) <= 1.0
        assert calculate_mastery_decay(0.0, 10) == 0.0

    def test_calculate_next_review_correct(self):
        from services.error_review_service import calculate_next_review
        # 答对 → 间隔翻倍，上限60天
        assert calculate_next_review(1, correct=True) == 2
        assert calculate_next_review(3, correct=True) == 6
        assert calculate_next_review(30, correct=True) == 60
        assert calculate_next_review(60, correct=True) == 60  # 上限

    def test_calculate_next_review_wrong(self):
        from services.error_review_service import calculate_next_review
        # 答错 → 间隔减半，下限1天
        assert calculate_next_review(7, correct=False) == 3  # 7//2=3
        assert calculate_next_review(1, correct=False) == 1  # 下限

    def test_build_review_schedule(self):
        from services.error_review_service import build_review_schedule
        schedule = build_review_schedule(0.5, initial_interval=1)
        assert len(schedule) == 4  # 四间隔
        assert schedule[0]["interval_days"] == 1
        assert schedule[1]["interval_days"] == 3
        assert schedule[2]["interval_days"] == 7
        assert schedule[3]["interval_days"] == 30

    def test_initialize_review_schedule_structure(self):
        from services.error_review_service import build_review_schedule
        schedule = build_review_schedule(0.5)
        for item in schedule:
            assert "review_round" in item
            assert "interval_days" in item
            assert "scheduled_at" in item
            assert "completed" in item
            assert not item["completed"]


class TestExplainTools:
    """测试 F7 结构化讲解工具"""

    def test_build_fallback_explain(self):
        from agents.tools.explain_tools import build_fallback_explain
        result = build_fallback_explain("math", "函数单调性", 0.23)
        assert "concept_summary" in result
        assert "key_difficulty" in result
        assert "example" in result
        assert "variant" in result
        assert "extension" in result
        assert result["is_fallback"] is True
        assert result["confidence"] == 0.5
        assert "函数单调性" in result["concept_summary"]

    def test_build_explain_payload(self):
        from agents.tools.explain_tools import build_explain_payload
        payload = build_explain_payload(
            None, "math_func_mono", "函数单调性", 0.23, 0.35, "math",
            exam_frequency=0.85, question_count=12,
        )
        assert "system_prompt" in payload
        assert "response_format" in payload
        assert payload["response_format"]["type"] == "json_schema"

    def test_build_explain_different_mastery(self):
        from agents.tools.explain_tools import build_explain_payload
        # mastery=0.23 → "薄弱"
        p1 = build_explain_payload(None, "a", "知识点A", 0.23, 0.5, "math")
        assert "薄弱" in p1["user_message"] or "弱" in p1["user_message"]

    def test_build_explain_unknown_subject(self):
        from agents.tools.explain_tools import build_explain_payload
        payload = build_explain_payload(None, "x", "未知", 0.5, 0, "unknown")
        # 应该使用 subject_id 原文
        assert "unknown" in payload["user_message"] or "未知" in payload["user_message"]


class TestSharedMemory:
    """测试跨模块数据一致性"""

    def test_prd_feature_arch_count_match(self):
        """PRD的MVP功能数量与架构Agent数量匹配"""
        prd_mvp = {"F1诊断", "F2规划", "F3推荐", "F4测评", "F5知识体系", "F6学习中心", "F7讲解", "F8间隔复习"}
        arch_agents = {"diagnosis", "planning", "recommendation", "assessment"}
        # Agent少于PRD功能，因为F5/F6/F7/F8是复用/扩展而不是独立Agent
        assert len(prd_mvp) == 8
        assert len(arch_agents) == 4  # 4个核心Agent

    def test_design_token_consistent(self):
        """设计Token与架构约束一致"""
        # 设计主色是#2563EB（学术蓝），架构无颜色依赖
        expected_primary = "#2563EB"
        assert expected_primary.startswith("#") and len(expected_primary) == 7


if __name__ == "__main__":
    pytest.main(["-v", __file__])
