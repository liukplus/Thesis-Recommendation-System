"""Unit tests for the agent layer."""
from __future__ import annotations

import pytest

from app.agent.guardrails import GuardrailController
from app.agent.tools import TOOL_REGISTRY
from app.agent.state import AgentState, PlanStep
from app.agent.planner import PlanFirstPlanner
from app.agent.loop import AgentRuntime


class TestGuardrails:
    """Tests for GuardrailController."""

    def test_step_limit(self):
        """Step limit guardrail should trigger at max steps."""
        guardrails = GuardrailController(max_steps=3)
        state = _make_state(step_idx=3)

        result = guardrails.check_all(state)
        assert result.should_stop is True
        assert "step" in result.reason.lower()

    def test_step_limit_not_triggered(self):
        """Step limit should not trigger before max steps."""
        guardrails = GuardrailController(max_steps=5)
        state = _make_state(step_idx=2)

        result = guardrails.check_all(state)
        assert result.should_stop is False

    def test_no_step_limit(self):
        """max_steps=0 means unlimited."""
        guardrails = GuardrailController(max_steps=0)
        state = _make_state(step_idx=100)

        result = guardrails.check_all(state)
        assert result.should_stop is False

    def test_loop_detection(self):
        """Same tool call 3x should trigger loop detection."""
        guardrails = GuardrailController(max_steps=10, loop_threshold=3)
        state = _make_state()

        # Same tool + args 3 times
        for _ in range(3):
            guardrails.record_tool_call("search", {"query": "test"})

        result = guardrails.check_all(state)
        assert result.should_stop is True
        assert "loop" in result.reason.lower()

    def test_loop_detection_different_args(self):
        """Different arguments should not trigger loop detection."""
        guardrails = GuardrailController(max_steps=10, loop_threshold=3)
        state = _make_state()

        guardrails.record_tool_call("search", {"query": "a"})
        guardrails.record_tool_call("search", {"query": "b"})
        guardrails.record_tool_call("search", {"query": "c"})

        result = guardrails.check_all(state)
        assert result.should_stop is False

    def test_consecutive_errors(self):
        """Too many consecutive errors should trigger."""
        guardrails = GuardrailController(max_steps=10, max_consecutive_errors=3)
        state = _make_state()

        for _ in range(3):
            guardrails.record_tool_error()

        result = guardrails.check_all(state)
        assert result.should_stop is True
        assert "error" in result.reason.lower()

    def test_success_resets_error_counter(self):
        """Successful tool call should reset consecutive error counter."""
        guardrails = GuardrailController(max_steps=10, max_consecutive_errors=3)
        state = _make_state()

        guardrails.record_tool_error()
        guardrails.record_tool_error()
        guardrails.record_tool_success()  # resets counter
        guardrails.record_tool_error()
        guardrails.record_tool_error()

        result = guardrails.check_all(state)
        assert result.should_stop is False  # only 2 consecutive


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_builtin_tools_registered(self):
        """Built-in tools should be registered."""
        assert TOOL_REGISTRY.has("get_help")
        assert TOOL_REGISTRY.has("echo")
        assert TOOL_REGISTRY.has("search_stub")
        assert TOOL_REGISTRY.has("summarize_stub")

    def test_tool_count(self):
        """Should have 4 built-in tools."""
        assert len(TOOL_REGISTRY.tool_names) == 4

    @pytest.mark.asyncio
    async def test_echo_tool(self):
        """Echo tool should return the message."""
        result = await TOOL_REGISTRY.execute("echo", {"message": "hello world"})
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_search_stub_tool(self):
        """Search stub should return mock results."""
        result = await TOOL_REGISTRY.execute(
            "search_stub", {"query": "AI", "max_results": 3}
        )
        assert isinstance(result, list)
        assert len(result) == 3
        assert "title" in result[0]
        assert "AI" in result[0]["title"]

    def test_unknown_tool_raises(self):
        """Executing unknown tool should raise ValidationError."""
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            import asyncio

            asyncio.run(TOOL_REGISTRY.execute("nonexistent", {}))

    def test_openai_format(self):
        """Tools should have valid OpenAI format."""
        tools = TOOL_REGISTRY.to_openai_format()
        assert len(tools) == 4
        for t in tools:
            assert t["type"] == "function"
            assert "name" in t["function"]
            assert "description" in t["function"]
            assert "parameters" in t["function"]


class TestPlanner:
    """Tests for the planner."""

    @pytest.mark.asyncio
    async def test_template_plan(self):
        """Template planner should generate reasonable plans."""
        planner = PlanFirstPlanner(llm=None)  # no LLM, use template
        steps = await planner.generate_plan("survey on deep learning papers")

        assert len(steps) >= 3
        assert steps[0].index == 1
        # Should have a search step
        assert any(s.tool == "search_stub" for s in steps)
        # Last step should be synthesis
        assert steps[-1].status == "pending"


class TestAgentState:
    """Tests for AgentState."""

    def test_initial_state(self):
        """Initial state should have correct defaults."""
        state = AgentState(goal="test goal")
        assert state.goal == "test goal"
        assert state.status == "pending"
        assert state.step_idx == 0
        assert state.is_finished is False
        assert state.total_tokens == 0
        assert state.task_id.startswith("agent_")

    def test_mark_completed(self):
        """Marking as completed should set status and answer."""
        state = AgentState(goal="test")
        state.mark_completed("The answer is 42")

        assert state.status == "completed"
        assert state.final_answer == "The answer is 42"
        assert state.is_finished is True
        assert state.finished_at is not None

    def test_mark_failed(self):
        """Marking as failed should set status and error."""
        state = AgentState(goal="test")
        state.mark_failed("Something went wrong")

        assert state.status == "failed"
        assert state.error == "Something went wrong"
        assert state.is_finished is True

    def test_plan_steps(self):
        """Plan steps should serialize correctly."""
        state = AgentState(goal="test")
        state.plan = [
            PlanStep(index=1, description="Step one", tool="search_stub"),
            PlanStep(index=2, description="Step two"),
        ]

        plan_dict = state.to_dict()["plan"]
        assert len(plan_dict) == 2
        assert plan_dict[0]["tool"] == "search_stub"


class TestAgentRuntime:
    """Tests for AgentRuntime (rule-based mode, no LLM)."""

    @pytest.mark.asyncio
    async def test_agent_simple_greeting(self):
        """Agent should respond to a simple greeting."""
        runtime = AgentRuntime(
            llm=None,
            tools=TOOL_REGISTRY,
            max_steps=3,
            plan_first=False,
        )

        state = await runtime.run("hello")

        assert state.status == "completed"
        assert len(state.final_answer) > 0
        assert state.step_idx >= 1

    @pytest.mark.asyncio
    async def test_agent_uses_search_tool(self):
        """Agent should use the search tool for research queries."""
        runtime = AgentRuntime(
            llm=None,
            tools=TOOL_REGISTRY,
            max_steps=3,
            plan_first=False,
        )

        state = await runtime.run("tell me about machine learning papers")

        assert state.status == "completed"
        # Should have used the search tool
        assert len(state.tool_calls) >= 1
        assert any(tc.name == "search_stub" for tc in state.tool_calls)
        # Final answer should mention papers/results
        assert len(state.final_answer) > 50

    @pytest.mark.asyncio
    async def test_agent_respects_max_steps(self):
        """Agent should not exceed max_steps."""
        runtime = AgentRuntime(
            llm=None,
            tools=TOOL_REGISTRY,
            max_steps=1,
            plan_first=False,
        )

        state = await runtime.run("deep learning research")

        assert state.step_idx <= 1  # should respect max steps

    @pytest.mark.asyncio
    async def test_agent_plan_first(self):
        """Agent with plan_first should generate a plan."""
        runtime = AgentRuntime(
            llm=None,
            tools=TOOL_REGISTRY,
            max_steps=3,
            plan_first=True,
        )

        state = await runtime.run("survey on transformers")

        assert state.status == "completed"
        assert len(state.plan) >= 3
        assert state.plan[0].index == 1


def _make_state(step_idx: int = 0):
    """Helper to create a simple AgentState for guardrail tests."""
    state = AgentState(goal="test")
    state.step_idx = step_idx
    return state
