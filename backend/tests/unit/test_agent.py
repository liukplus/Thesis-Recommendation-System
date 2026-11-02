"""Unit tests for the agent layer."""
from __future__ import annotations

import pytest
from app.agent.guardrails import GuardrailController
from app.agent.planner import PlanFirstPlanner
from app.agent.state import AgentState, PlanStep
from app.agent.tools import TOOL_REGISTRY
from app.graphs.agent import build_agent_graph, serialize_agent_state
from app.graphs.llm import get_chat_model


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
        assert TOOL_REGISTRY.has("run_research")

    def test_tool_count(self):
        """Should have 2 built-in tools."""
        assert len(TOOL_REGISTRY.tool_names) == 2

    @pytest.mark.asyncio
    async def test_get_help_tool(self):
        """get_help should list the available tools."""
        result = await TOOL_REGISTRY.execute("get_help", {})
        assert "run_research" in result

    @pytest.mark.asyncio
    async def test_run_research_tool(self):
        """run_research should delegate to the pipeline and return a typed result."""
        result = await TOOL_REGISTRY.execute("run_research", {"query": "deep learning"})
        assert isinstance(result, dict)
        assert "answer" in result
        assert "papers" in result

    def test_unknown_tool_raises(self):
        """Executing unknown tool should raise ValidationError."""
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            import asyncio

            asyncio.run(TOOL_REGISTRY.execute("nonexistent", {}))

    def test_openai_format(self):
        """Tools should have valid OpenAI format."""
        tools = TOOL_REGISTRY.to_openai_format()
        assert len(tools) == 2
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
        # Should have a research step
        assert any(s.tool == "run_research" for s in steps)
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
            PlanStep(index=1, description="Step one", tool="run_research"),
            PlanStep(index=2, description="Step two"),
        ]

        plan_dict = state.to_dict()["plan"]
        assert len(plan_dict) == 2
        assert plan_dict[0]["tool"] == "run_research"


class TestAgentGraph:
    """Tests for the compiled agent graph in rule-based mode (no LLM client)."""

    async def _run_graph(
        self,
        goal: str,
        *,
        max_steps: int = 3,
        plan_first: bool = False,
    ) -> dict:
        graph = build_agent_graph(
            get_chat_model(None),
            max_steps=max_steps,
            plan_first=plan_first,
        )
        state = await graph.ainvoke(
            {"goal": goal, "messages": [], "task_id": "agent_test"}
        )
        return serialize_agent_state(state)

    async def test_agent_simple_greeting(self):
        """Agent should respond to a simple greeting."""
        data = await self._run_graph("hello")

        assert data["status"] == "completed"
        assert len(data["final_answer"]) > 0
        assert data["steps"] >= 1

    async def test_agent_uses_research_tool(self):
        """Agent should delegate to run_research for research queries."""
        data = await self._run_graph("tell me about machine learning papers")

        assert data["status"] == "completed"
        assert any(tc["name"] == "run_research" for tc in data["tool_calls"])
        assert len(data["final_answer"]) > 50

    async def test_agent_respects_max_steps(self):
        """Agent should not exceed max_steps."""
        data = await self._run_graph("deep learning research", max_steps=1)

        assert data["steps"] <= 1

    async def test_agent_plan_first(self):
        """Agent with plan_first should generate a plan."""
        data = await self._run_graph("survey on transformers", plan_first=True)

        assert data["status"] == "completed"
        assert len(data["plan"]) >= 3
        assert data["plan"][0]["index"] == 1


def _make_state(step_idx: int = 0):
    """Helper to create a simple AgentState for guardrail tests."""
    state = AgentState(goal="test")
    state.step_idx = step_idx
    return state
