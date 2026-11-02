"""LangGraph-compiled research pipeline.

Replaces ``app/pipeline/orchestrator.py::PipelineOrchestrator`` with a compiled
``StateGraph`` over the same 8 ``BaseStage`` subclasses. Each stage becomes a node
that reuses ``BaseStage.run`` (timing + ``StageResult`` recording) — only the
sequential orchestration loop is replaced by the graph.

D10 adaptation: LangGraph state moves through immutable channel updates, so the
"single context object" is represented by rebuilding a fresh ``PipelineContext``
per node from the state snapshot (``_state_to_context``). ``PipelineData`` stays
the single typed cross-stage carrier; prior ``stage_results`` are restored so a
node sees the whole run so far. Run-level timing therefore lives in the sum of
per-stage ``duration_ms`` values (as in ``serialize_pipeline_state``), not in a
rebuilt context's ``started_at``.

State channels:
- ``data`` is a typed ``PipelineData`` (REPLACE semantics): each node returns the
  full, mutated carrier.
- ``stage_results`` uses an append reducer; each node appends only the result its
  stage recorded.
"""
from __future__ import annotations

import contextlib
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.domain.paper import paper_to_wire
from app.domain.pipeline import PipelineData
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext, StageResult


def _append(left: Any, right: Any) -> list:
    """Append-merge reducer for ``stage_results``."""
    return list(left or []) + list(right or [])


class PipelineState(TypedDict, total=False):
    """State for the compiled pipeline graph."""

    query: str
    trace_id: str
    data: PipelineData
    stage_results: Annotated[list, _append]


def _copy_pipeline_data(data: Any) -> PipelineData:
    """Coerce a state ``data`` value into a fresh ``PipelineData`` instance.

    The first node may receive an empty dict (from an untyped caller); every later
    node receives the ``PipelineData`` the previous node returned. Deep-copy so a
    stage never mutates another stage's carrier.
    """
    if isinstance(data, PipelineData):
        return data.model_copy(deep=True)
    return PipelineData()


def _state_to_context(state: PipelineState) -> PipelineContext:
    """Rebuild a ``PipelineContext`` from a graph state snapshot."""
    ctx = PipelineContext(query=state.get("query", ""))
    trace_id = state.get("trace_id")
    if trace_id:
        ctx.trace_id = trace_id
    ctx.state = _copy_pipeline_data(state.get("data"))
    ctx.stage_results = [
        StageResult(
            stage_name=r["name"],
            success=r.get("success", True),
            duration_ms=r.get("duration_ms") or 0.0,
            error=r.get("error"),
        )
        for r in state.get("stage_results") or []
    ]
    return ctx


def _context_to_delta(ctx: PipelineContext, prior_results: int = 0) -> dict[str, Any]:
    """Turn a context into a graph-state update.

    Only results appended after ``prior_results`` (i.e. by this node's stage) are
    emitted; the earlier ones were restored from state and must not be appended
    again by the ``stage_results`` reducer.
    """
    results = [
        {
            "name": r.stage_name,
            "success": r.success,
            "duration_ms": round(r.duration_ms, 2),
            "error": r.error,
        }
        for r in ctx.stage_results[prior_results:]
    ]
    return {
        "data": ctx.state,
        "stage_results": results,
        "query": ctx.query,
        "trace_id": ctx.trace_id,
    }


def _make_stage_node(stage: BaseStage):
    """Wrap a ``BaseStage`` as a graph node that runs it and returns a state delta."""

    async def node(state: PipelineState) -> dict[str, Any]:
        ctx = _state_to_context(state)
        prior_results = len(ctx.stage_results)
        # ``run`` re-raises after recording the failure on the stage result, so
        # only the error propagation is suppressed here.
        with contextlib.suppress(Exception):
            await stage.run(ctx)
        return _context_to_delta(ctx, prior_results)

    return node


def default_pipeline_stages() -> list[BaseStage]:
    """Return the default 8 pipeline stages, in execution order."""
    from app.pipeline.stages.stage1_query import QueryParseStage
    from app.pipeline.stages.stage2_recall import RecallStage
    from app.pipeline.stages.stage3_fusion import FusionStage
    from app.pipeline.stages.stage4_rerank import RerankStage
    from app.pipeline.stages.stage5_evidence import EvidenceExtractionStage
    from app.pipeline.stages.stage6_survey import SurveyGenerationStage
    from app.pipeline.stages.stage7_verify import CitationVerificationStage
    from app.pipeline.stages.stage8_export import ExportStage

    return [
        QueryParseStage(),
        RecallStage(),
        FusionStage(),
        RerankStage(),
        EvidenceExtractionStage(),
        SurveyGenerationStage(),
        CitationVerificationStage(),
        ExportStage(),
    ]


def build_pipeline_graph(
    stages: list[BaseStage] | None = None,
    *,
    stop_on_error: bool = True,
):
    """Compile the pipeline into a ``StateGraph``.

    Args:
        stages: Ordered stages; defaults to ``default_pipeline_stages()``.
        stop_on_error: When True (default, matching the deterministic-first
            policy D2), the first failed stage ends the run. When False, later
            stages still run on partial state and the final result reports
            ``success=False``.

    Returns:
        A compiled LangGraph state graph.
    """
    stages = list(stages if stages is not None else default_pipeline_stages())
    if not stages:
        return StateGraph(PipelineState).compile()

    def route_after_stage(state: PipelineState) -> str:
        """Continue to the next stage, or stop after the first failure."""
        results = state.get("stage_results") or []
        if stop_on_error and results and not results[-1].get("success", True):
            return "stop"
        return "next"

    graph = StateGraph(PipelineState)
    for stage in stages:
        graph.add_node(stage.name, _make_stage_node(stage))

    graph.add_edge(START, stages[0].name)
    for current, following in zip(stages, stages[1:], strict=False):
        graph.add_conditional_edges(
            current.name,
            route_after_stage,
            {"next": following.name, "stop": END},
        )
    graph.add_conditional_edges(
        stages[-1].name,
        route_after_stage,
        {"next": END, "stop": END},
    )

    return graph.compile()


def serialize_pipeline_state(state: dict[str, Any]) -> dict[str, Any]:
    """Map a compiled-pipeline final state to the ``PipelineRunResponse`` shape."""
    data = state.get("data")
    pipeline = data if isinstance(data, PipelineData) else PipelineData()

    papers = [paper_to_wire(p) for p in pipeline.ranked]
    answer = pipeline.verified.answer if pipeline.verified else ""
    formats = list(pipeline.exports.formats.keys()) if pipeline.exports else []

    stage_results = state.get("stage_results") or []
    success = bool(stage_results) and all(r.get("success", True) for r in stage_results)

    return {
        "trace_id": state.get("trace_id", ""),
        "query": state.get("query", ""),
        "success": success,
        "total_duration_ms": round(
            sum((r.get("duration_ms") or 0) for r in stage_results), 2
        ),
        "stages": [
            {
                "name": r["name"],
                "success": r.get("success", True),
                "duration_ms": round(r.get("duration_ms") or 0, 2),
            }
            for r in stage_results
        ],
        "answer": answer,
        "papers": papers,
        "export_formats": formats,
    }
