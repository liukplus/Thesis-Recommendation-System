"""Unit tests for the pipeline framework (compiled graph)."""
from __future__ import annotations

import pytest
from app.domain.paper import Paper
from app.domain.pipeline import PipelineData
from app.graphs.pipeline import (
    build_pipeline_graph,
    default_pipeline_stages,
    serialize_pipeline_state,
)
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext


class SuccessStage(BaseStage):
    """A stage that always succeeds."""

    def __init__(self, name: str = "success") -> None:
        super().__init__(name=name)

    async def _execute(self, ctx: PipelineContext) -> None:
        ctx.state.recalled.append(Paper(paper_id=self.name, title=self.name))


class FailingStage(BaseStage):
    """A stage that always fails."""

    def __init__(self, name: str = "failing") -> None:
        super().__init__(name=name)

    async def _execute(self, ctx: PipelineContext) -> None:
        raise ValueError("Intentional test failure")


@pytest.mark.asyncio
async def test_pipeline_runs_all_stages():
    """Pipeline graph should run all stages in order."""
    stages = [SuccessStage("s1"), SuccessStage("s2"), SuccessStage("s3")]
    graph = build_pipeline_graph(stages)

    state = await graph.ainvoke(
        {"query": "test query", "data": PipelineData(), "stage_results": []}
    )

    results = state["stage_results"]
    assert len(results) == 3
    assert [r["name"] for r in results] == ["s1", "s2", "s3"]
    assert [p.paper_id for p in state["data"].recalled] == ["s1", "s2", "s3"]


def test_pipeline_stage_names():
    """Default pipeline stages should be the 8 well-known names, in order."""
    names = [s.name for s in default_pipeline_stages()]
    assert names == [
        "query_parse",
        "recall",
        "fusion",
        "rerank",
        "evidence_extraction",
        "survey_generation",
        "citation_verification",
        "export",
    ]


@pytest.mark.asyncio
async def test_pipeline_stop_on_error_by_default():
    """Default semantics: a failed stage aborts the rest of the pipeline."""
    stages = [SuccessStage("s1"), FailingStage("s2"), SuccessStage("s3")]
    graph = build_pipeline_graph(stages)

    state = await graph.ainvoke(
        {"query": "test", "data": PipelineData(), "stage_results": []}
    )

    results = state["stage_results"]
    assert [r["name"] for r in results] == ["s1", "s2"]
    assert results[1]["success"] is False
    assert serialize_pipeline_state(state)["success"] is False


@pytest.mark.asyncio
async def test_pipeline_continue_on_error():
    """With ``stop_on_error=False`` the failure is recorded but stages continue."""
    stages = [SuccessStage("s1"), FailingStage("s2"), SuccessStage("s3")]
    graph = build_pipeline_graph(stages, stop_on_error=False)

    state = await graph.ainvoke(
        {"query": "test", "data": PipelineData(), "stage_results": []}
    )
    data = serialize_pipeline_state(state)

    results = state["stage_results"]
    assert len(results) == 3
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert results[1]["error"] == "Intentional test failure"
    assert results[2]["success"] is True
    assert data["success"] is False


def test_pipeline_context_trace_id():
    """Pipeline context should have a trace ID."""
    ctx = PipelineContext(query="test")
    assert ctx.trace_id is not None
    assert len(ctx.trace_id) == 32  # 16 bytes hex = 32 chars
