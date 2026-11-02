"""Unit tests for the LangGraph-based agent and pipeline graphs."""
from __future__ import annotations

import asyncio
import json

from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.domain.pipeline import PipelineData
from app.domain.survey import Citation, Survey
from app.graphs.agent import build_agent_graph, serialize_agent_state
from app.graphs.pipeline import build_pipeline_graph
from app.graphs.streaming import agent_stream_events, pipeline_stream_events
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext
from langchain_core.messages import AIMessage, ToolMessage

# ---------------------------------------------------------------------------
# Agent graph
# ---------------------------------------------------------------------------


class TestAgentGraph:
    async def test_completes_with_final_answer(self, fake_chat_model):
        model = fake_chat_model([AIMessage(content="the final answer")])
        graph = build_agent_graph(model, plan_first=False, max_steps=3)

        result = await graph.ainvoke({"goal": "hello", "messages": []})

        assert result["status"] == "completed"
        assert result["final_answer"] == "the final answer"

    async def test_routes_through_tools_and_records_tool_message(self, fake_chat_model):
        think = AIMessage(
            content="thinking",
            tool_calls=[{
                "name": "run_research",
                "args": {"query": "AI"},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        model = fake_chat_model([think, AIMessage(content="found papers")])
        graph = build_agent_graph(model, plan_first=False, max_steps=4)

        result = await graph.ainvoke({"goal": "papers about AI", "messages": []})

        assert any(isinstance(m, ToolMessage) for m in result["messages"])
        assert result["status"] == "completed"
        assert result["final_answer"] == "found papers"

    async def test_plan_first_populates_plan(self, fake_chat_model):
        model = fake_chat_model([AIMessage(content="done")])
        graph = build_agent_graph(model, plan_first=True, max_steps=3)

        result = await graph.ainvoke({"goal": "survey on transformers", "messages": []})

        assert len(result["plan"]) >= 3
        assert result["plan"][0]["index"] == 1

    async def test_step_limit_fails(self, fake_chat_model):
        # Script an agent that keeps calling the research tool forever.
        think = AIMessage(
            content="thinking",
            tool_calls=[{
                "name": "run_research",
                "args": {"query": "x"},
                "id": "call_loop",
                "type": "tool_call",
            }],
        )
        model = fake_chat_model([think])
        graph = build_agent_graph(model, plan_first=False, max_steps=2)

        result = await graph.ainvoke({"goal": "papers about x", "messages": []})

        assert result["status"] == "failed"
        assert "step limit" in (result.get("error") or "").lower()

    async def test_loop_detection_stops(self, fake_chat_model):
        """Repeating the identical tool call trips the loop guardrail (D2)."""
        think = AIMessage(
            content="thinking",
            tool_calls=[{
                "name": "run_research",
                "args": {"query": "loop"},
                "id": "call_loop",
                "type": "tool_call",
            }],
        )
        model = fake_chat_model([think])
        graph = build_agent_graph(
            model, plan_first=False, max_steps=10, loop_threshold=3
        )

        result = await graph.ainvoke({"goal": "papers about loops", "messages": []})

        assert result["status"] == "failed"
        assert "loop" in (result.get("error") or "").lower()

    async def test_consecutive_errors_circuit_breaks(self, fake_chat_model):
        """Three failing tool calls trip the consecutive-error circuit breaker (D2)."""
        thinks = [
            AIMessage(
                content="thinking",
                tool_calls=[{
                    "name": "does_not_exist",
                    "args": {"q": q},
                    "id": f"call_err_{i}",
                    "type": "tool_call",
                }],
            )
            for i, q in enumerate(("a", "b", "c"))
        ]
        model = fake_chat_model(thinks)
        graph = build_agent_graph(
            model, plan_first=False, max_steps=10, max_consecutive_errors=3
        )

        result = await graph.ainvoke({"goal": "papers about x", "messages": []})

        assert result["status"] == "failed"
        assert "error" in (result.get("error") or "").lower()

    async def test_llm_failure_marks_run_failed(self, raising_chat_model):
        """A model/network error fails the run instead of propagating (parity with
        the old AgentRuntime, which caught think-step errors)."""
        graph = build_agent_graph(raising_chat_model(), plan_first=False, max_steps=3)

        result = await graph.ainvoke({"goal": "hi", "messages": []})

        assert result["status"] == "failed"
        assert (result.get("error") or "").startswith("LLM error:")

    async def test_llm_failure_stream_emits_single_error_then_end(self, raising_chat_model):
        graph = build_agent_graph(raising_chat_model(), plan_first=False, max_steps=3)

        events = [
            e
            async for e in agent_stream_events(graph, {"goal": "hi", "messages": []})
        ]

        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert errors[0]["error"].startswith("LLM error:")
        assert events[-1]["type"] == "end"
        assert not any(e["type"] == "final_answer" for e in events)

    async def test_token_budget_stops_agent(self, fake_chat_model):
        """Cumulative tokens beyond the cap fail with a budget reason (D2)."""
        think = AIMessage(
            content="thinking",
            tool_calls=[{
                "name": "run_research",
                "args": {"query": "x"},
                "id": "call_budget",
                "type": "tool_call",
            }],
            usage_metadata={
                "input_tokens": 5,
                "output_tokens": 2,
                "total_tokens": 7,
            },
        )
        model = fake_chat_model([think])
        graph = build_agent_graph(
            model, plan_first=False, max_steps=10, max_total_tokens=1
        )

        result = await graph.ainvoke({"goal": "papers about x", "messages": []})

        assert result["status"] == "failed"
        assert "budget" in (result.get("error") or "").lower()
        # Token accounting from ``usage_metadata`` must actually accumulate.
        assert result["usage"]["total_tokens"] == 7

    def test_serialize_agent_state(self):
        state = {
            "messages": [AIMessage(content="the answer")],
            "goal": "hello",
            "task_id": "agent_1",
            "steps": 1,
            "status": "completed",
            "final_answer": "the answer",
            "plan": [{"index": 1, "description": "do the thing", "status": "pending", "tool": None}],
            "error": None,
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

        out = serialize_agent_state(state)

        assert out["task_id"] == "agent_1"
        assert out["status"] == "completed"
        assert out["final_answer"] == "the answer"
        assert out["steps"] == 1
        assert out["usage"]["total_tokens"] == 3
        assert out["plan"][0]["index"] == 1


# ---------------------------------------------------------------------------
# Pipeline graph
# ---------------------------------------------------------------------------


class StubStage(BaseStage):
    def __init__(self, name: str) -> None:
        super().__init__(name=name)

    async def _execute(self, ctx: PipelineContext) -> None:
        ctx.state.recalled.append(Paper(paper_id=self.name, title=self.name))


class SlowStage(BaseStage):
    """A stage that takes a measurable amount of wall-clock time."""

    def __init__(self, name: str, delay: float = 0.01) -> None:
        super().__init__(name=name)
        self.delay = delay

    async def _execute(self, ctx: PipelineContext) -> None:
        await asyncio.sleep(self.delay)


class BadStage(BaseStage):
    """A stage that always fails."""

    def __init__(self, name: str = "bad") -> None:
        super().__init__(name=name)

    async def _execute(self, ctx: PipelineContext) -> None:
        raise ValueError("boom")


class TestPipelineGraph:
    async def test_runs_stages_in_order(self):
        stages = [StubStage("s1"), StubStage("s2"), StubStage("s3")]
        graph = build_pipeline_graph(stages)

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        names = [r["name"] for r in result["stage_results"]]
        assert names == ["s1", "s2", "s3"]
        assert [p.paper_id for p in result["data"].recalled] == ["s1", "s2", "s3"]

    async def test_failing_stage_aborts_pipeline_by_default(self):
        """Default stop-on-error semantics (D2): later stages never run."""
        stages = [StubStage("s1"), BadStage(), StubStage("s3")]
        graph = build_pipeline_graph(stages)

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        names = [r["name"] for r in result["stage_results"]]
        assert names == ["s1", "bad"]
        assert result["stage_results"][1]["success"] is False
        assert result["stage_results"][1]["error"] == "boom"

    async def test_failing_stage_can_continue_when_opted_in(self):
        """``stop_on_error=False`` records the failure but keeps going."""
        stages = [StubStage("s1"), BadStage(), StubStage("s3")]
        graph = build_pipeline_graph(stages, stop_on_error=False)

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        assert result["stage_results"][0]["success"] is True
        assert result["stage_results"][1]["success"] is False
        assert result["stage_results"][1]["error"] == "boom"
        assert result["stage_results"][2]["success"] is True

    async def test_stage5_mock_evidence_marked_non_verbatim(self):
        """D9 honesty: synthesized skeleton spans must not claim verbatim match."""
        from app.pipeline.stages.stage5_evidence import EvidenceExtractionStage

        class RankedPaperStage(BaseStage):
            def __init__(self) -> None:
                super().__init__(name="rank")

            async def _execute(self, ctx: PipelineContext) -> None:
                ctx.state.ranked = [
                    Paper(paper_id="p1", title="t", abstract="x" * 200),
                ]

        graph = build_pipeline_graph([RankedPaperStage(), EvidenceExtractionStage()])

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        chunks = result["data"].evidence
        assert chunks
        assert all(chunk.verbatim is False for chunk in chunks)

    async def test_stage7_l1_filters_unknown_citations(self):
        """D8-L1: citations whose source is absent from evidence are dropped."""
        from app.pipeline.stages.stage7_verify import CitationVerificationStage

        class PlantSurveyStage(BaseStage):
            def __init__(self) -> None:
                super().__init__(name="plant")

            async def _execute(self, ctx: PipelineContext) -> None:
                ctx.state.evidence = [
                    EvidenceChunk(
                        chunk_id="ev1", paper_id="real", content="span", anchor="span"
                    ),
                ]
                ctx.state.survey = Survey(
                    answer="ans",
                    citations=[
                        Citation(index=1, paper_id="real"),
                        Citation(index=2, paper_id="ghost"),
                    ],
                )

        graph = build_pipeline_graph([PlantSurveyStage(), CitationVerificationStage()])

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        verified = result["data"].verified
        assert [c.paper_id for c in verified.citations] == ["real"]

    async def test_export_after_failure_reports_failure(self):
        """With continue-on-error, stage 8 must export run-wide success=False."""
        from app.pipeline.stages.stage8_export import ExportStage

        stages = [SlowStage("s1", delay=0.01), BadStage(), ExportStage()]
        graph = build_pipeline_graph(stages, stop_on_error=False)

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        exported = json.loads(result["data"].exports.formats["json"])
        assert exported["success"] is False
        assert exported["total_duration_ms"] >= 10

    async def test_export_json_reports_aggregate_run_metrics(self):
        """Stage-8 JSON export must see the whole run, not a per-node fresh context.

        Regression for the per-node ``PipelineContext`` rebuild (D10 adaptation):
        the export node previously saw ``total_duration_ms`` ~ 0 (fresh
        ``started_at``) and only its own stage result.
        """
        from app.pipeline.stages.stage8_export import ExportStage

        stages = [SlowStage("s1", delay=0.01), ExportStage()]
        graph = build_pipeline_graph(stages, stop_on_error=False)

        result = await graph.ainvoke(
            {"query": "test", "data": PipelineData(), "stage_results": []}
        )

        # The append reducer must not double-count restored prior results.
        assert len(result["stage_results"]) == 2
        exported = json.loads(result["data"].exports.formats["json"])
        assert exported["success"] is True
        assert exported["total_duration_ms"] >= 10


# ---------------------------------------------------------------------------
# Streaming adapters
# ---------------------------------------------------------------------------


class TestStreamingAdapters:
    async def test_agent_stream_emits_legacy_events(self, fake_chat_model):
        think = AIMessage(
            content="thinking",
            tool_calls=[{
                "name": "run_research",
                "args": {"query": "AI"},
                "id": "call_1",
                "type": "tool_call",
            }],
        )
        model = fake_chat_model([think, AIMessage(content="answer")])
        graph = build_agent_graph(model, plan_first=False, max_steps=4)

        events = [
            e
            async for e in agent_stream_events(graph, {"goal": "papers about AI", "messages": []})
        ]
        types = {e["type"] for e in events}

        assert "thought" in types
        assert "tool_call" in types
        assert "tool_result" in types
        assert "final_answer" in types
        assert "end" in types

    async def test_pipeline_stream_emits_legacy_events(self):
        stages = [StubStage("s1"), StubStage("s2")]
        graph = build_pipeline_graph(stages)

        events = [
            e
            async for e in pipeline_stream_events(
                graph,
                {"query": "q", "data": PipelineData(), "stage_results": []},
                stage_names=["s1", "s2"],
            )
        ]

        types = [e["type"] for e in events]
        assert types[0] == "start"
        assert "stage_start" in types
        assert "stage_complete" in types
        assert types[-1] == "complete"

    async def test_pipeline_stream_failure_ends_with_complete(self):
        """A failed stage emits ``error`` but the stream still terminates with
        ``complete`` (success=False) — the frontend has no bare-error terminal."""
        stages = [StubStage("s1"), BadStage(), StubStage("s3")]
        graph = build_pipeline_graph(stages)

        events = [
            e
            async for e in pipeline_stream_events(
                graph,
                {"query": "q", "data": PipelineData(), "stage_results": []},
                stage_names=["s1", "bad", "s3"],
            )
        ]

        types = [e["type"] for e in events]
        assert "error" in types
        error = next(e for e in events if e["type"] == "error")
        assert error["stage"] == "bad"
        assert types[-1] == "complete"
        complete = events[-1]
        assert complete["success"] is False
        # Stop-on-error: s3 never runs and is not reported as completed.
        assert not any(
            e.get("stage") == "s3" and e["type"] == "stage_complete" for e in events
        )

    async def test_agent_stream_respects_recursion_limit(self, fake_chat_model):
        """A long agent run must not die on LangGraph's default 25-superstep cap.

        14 tool rounds + final answer need ~30 supersteps; the caller-supplied
        ``recursion_limit`` must reach ``graph.astream``.
        """
        from langchain_core.tools import tool

        @tool
        async def echo(query: str) -> str:
            """Echo the query back."""
            return query

        responses = [
            AIMessage(
                content=f"thinking {i}",
                tool_calls=[{
                    "name": "echo",
                    "args": {"query": f"q{i}"},
                    "id": f"call_{i}",
                    "type": "tool_call",
                }],
            )
            for i in range(14)
        ]
        responses.append(AIMessage(content="done"))
        model = fake_chat_model(responses)
        graph = build_agent_graph(model, tools=[echo], plan_first=False, max_steps=15)

        events = [
            e
            async for e in agent_stream_events(
                graph,
                {"goal": "long running", "messages": []},
                config={"recursion_limit": 15 * 2 + 4},
            )
        ]

        types = [e["type"] for e in events]
        assert "error" not in types
        assert "final_answer" in types
