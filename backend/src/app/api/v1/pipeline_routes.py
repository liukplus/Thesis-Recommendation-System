"""Pipeline API endpoints.

Provides endpoints for running the 8-stage research pipeline,
both synchronously and via SSE streaming.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import LLMClientDep, SettingsDep
from app.core.ids import ensure_trace_id
from app.core.logging import get_logger
from app.domain.pipeline import PipelineData
from app.graphs.pipeline import (
    build_pipeline_graph,
    default_pipeline_stages,
    serialize_pipeline_state,
)
from app.graphs.streaming import pipeline_stream_events

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineRunRequest(BaseModel):
    """Request to run the pipeline."""

    query: str = Field(..., min_length=1, max_length=2000, description="Research query")
    max_papers: int = Field(default=20, ge=1, le=100, description="Max papers to return")
    stream: bool = Field(default=False, description="Whether to stream progress")


class PipelineRunResponse(BaseModel):
    """Response from a pipeline run."""

    trace_id: str
    query: str
    success: bool
    total_duration_ms: float
    stages: list[dict]
    answer: str = ""
    papers: list[dict] = Field(default_factory=list)
    export_formats: list[str] = Field(default_factory=list)


@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(
    req: PipelineRunRequest,
    settings: SettingsDep,
    llm: LLMClientDep,
) -> PipelineRunResponse:
    """Run the full research pipeline synchronously.

    Returns the complete result when all stages finish.
    """
    ensure_trace_id()
    logger.info(f"Pipeline run requested: {req.query[:80]}...")

    graph = build_pipeline_graph()
    initial = {"query": req.query, "data": PipelineData(), "stage_results": []}
    state = await graph.ainvoke(initial)

    return PipelineRunResponse(**serialize_pipeline_state(state))


@router.post("/run-stream")
async def run_pipeline_stream(
    req: PipelineRunRequest,
    settings: SettingsDep,
    llm: LLMClientDep,
) -> StreamingResponse:
    """Run the pipeline with SSE streaming progress updates.

    Events:
    - start: pipeline started
    - stage_start: a stage is starting
    - stage_complete: a stage completed
    - complete: pipeline finished (includes final result)
    - error: an error occurred
    """
    ensure_trace_id()

    stages = default_pipeline_stages()
    stage_names = [stage.name for stage in stages]
    graph = build_pipeline_graph(stages)
    initial = {"query": req.query, "data": PipelineData(), "stage_results": []}

    async def event_generator():
        """Generate SSE events from the compiled pipeline graph."""
        async for event in pipeline_stream_events(graph, initial, stage_names=stage_names):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stages")
async def list_stages() -> dict:
    """List all pipeline stages."""
    stages = default_pipeline_stages()
    return {
        "stages": [
            {"name": s.name, "index": i + 1}
            for i, s in enumerate(stages)
        ],
    }
