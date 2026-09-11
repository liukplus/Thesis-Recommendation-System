"""Pipeline API endpoints.

Provides endpoints for running the 8-stage research pipeline,
both synchronously and via SSE streaming.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import LLMClientDep, SettingsDep
from app.core.ids import ensure_trace_id
from app.core.logging import get_logger
from app.pipeline.context import PipelineContext
from app.pipeline.orchestrator import (
    PipelineOrchestrator,
    create_default_pipeline,
)

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

    pipeline = create_default_pipeline()
    ctx = PipelineContext(query=req.query)

    try:
        ctx = await pipeline.run(ctx)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        # Return partial results even on failure
        pass

    # Build response
    reranked = ctx.get_state("reranked_papers", {})
    papers = reranked.get("top_k", [])

    answer_data = ctx.get_state("generated_answer", {})
    answer = answer_data.get("answer", "")

    export = ctx.get_state("export", {})
    formats = list(export.get("formats", {}).keys()) if export else []

    return PipelineRunResponse(
        trace_id=ctx.trace_id,
        query=ctx.query,
        success=ctx.success,
        total_duration_ms=round(ctx.total_duration_ms, 2),
        stages=[
            {"name": r.stage_name, "success": r.success, "duration_ms": round(r.duration_ms, 2)}
            for r in ctx.stage_results
        ],
        answer=answer,
        papers=papers,
        export_formats=formats,
    )


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
    pipeline = create_default_pipeline()
    ctx = PipelineContext(query=req.query)

    queue: asyncio.Queue[str] = asyncio.Queue()

    async def event_generator():
        """Generate SSE events as the pipeline runs."""
        import json

        # Send start event
        yield f"data: {json.dumps({'type': 'start', 'trace_id': ctx.trace_id, 'query': ctx.query})}\n\n"

        # Progress callback
        async def progress_cb(stage_name: str, idx: int, total: int, pctx: PipelineContext):
            event = {
                "type": "stage_complete",
                "stage": stage_name,
                "progress": idx / total,
                "stage_index": idx,
                "total_stages": total,
                "success": pctx.stage_results[-1].success if pctx.stage_results else True,
                "duration_ms": round(pctx.stage_results[-1].duration_ms, 2) if pctx.stage_results else 0,
            }
            await queue.put(json.dumps(event))

        # Stage start events via custom wrapper
        total = len(pipeline.stages)
        for i, stage in enumerate(pipeline.stages):
            start_event = {
                "type": "stage_start",
                "stage": stage.name,
                "stage_index": i + 1,
                "total_stages": total,
                "progress": i / total,
            }
            yield f"data: {json.dumps(start_event)}\n\n"

            # Run just this stage
            try:
                await stage.run(ctx)
            except Exception as e:
                error_event = {
                    "type": "error",
                    "stage": stage.name,
                    "error": str(e),
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                break

            # Stage complete event
            stage_result = ctx.stage_results[-1]
            complete_event = {
                "type": "stage_complete",
                "stage": stage.name,
                "stage_index": i + 1,
                "total_stages": total,
                "progress": (i + 1) / total,
                "success": stage_result.success,
                "duration_ms": round(stage_result.duration_ms, 2),
            }
            yield f"data: {json.dumps(complete_event)}\n\n"

        ctx.finish()

        # Final result
        reranked = ctx.get_state("reranked_papers", {})
        papers = reranked.get("top_k", [])
        answer_data = ctx.get_state("generated_answer", {})
        answer = answer_data.get("answer", "")

        final_event = {
            "type": "complete",
            "success": ctx.success,
            "total_duration_ms": round(ctx.total_duration_ms, 2),
            "answer": answer,
            "papers": papers,
            "stages": [
                {"name": r.stage_name, "success": r.success, "duration_ms": round(r.duration_ms, 2)}
                for r in ctx.stage_results
            ],
        }
        yield f"data: {json.dumps(final_event)}\n\n"
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
    pipeline = create_default_pipeline()
    return {
        "stages": [
            {"name": s.name, "index": i + 1}
            for i, s in enumerate(pipeline.stages)
        ],
    }
