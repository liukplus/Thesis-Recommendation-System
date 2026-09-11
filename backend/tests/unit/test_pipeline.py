"""Unit tests for the pipeline framework."""
from __future__ import annotations

import pytest

from app.pipeline.context import PipelineContext
from app.pipeline.base import BaseStage
from app.pipeline.orchestrator import PipelineOrchestrator


class SuccessStage(BaseStage):
    """A stage that always succeeds."""

    def __init__(self, name: str = "success") -> None:
        super().__init__(name=name)

    async def _execute(self, ctx: PipelineContext) -> None:
        ctx.set_state(f"{self.name}_ran", True)


class FailingStage(BaseStage):
    """A stage that always fails."""

    def __init__(self, name: str = "failing") -> None:
        super().__init__(name=name)

    async def _execute(self, ctx: PipelineContext) -> None:
        raise ValueError("Intentional test failure")


class SlowStage(BaseStage):
    """A stage that takes some time (for cancellation tests)."""

    def __init__(self, name: str = "slow", delay: float = 0.1) -> None:
        super().__init__(name=name)
        self.delay = delay

    async def _execute(self, ctx: PipelineContext) -> None:
        import asyncio

        await asyncio.sleep(self.delay)
        ctx.set_state("slow_ran", True)


@pytest.mark.asyncio
async def test_pipeline_runs_all_stages():
    """Pipeline should run all stages in order."""
    stages = [SuccessStage("s1"), SuccessStage("s2"), SuccessStage("s3")]
    pipeline = PipelineOrchestrator(stages)
    ctx = PipelineContext(query="test query")

    ctx = await pipeline.run(ctx)

    assert ctx.success is True
    assert len(ctx.stage_results) == 3
    assert ctx.get_state("s1_ran") is True
    assert ctx.get_state("s2_ran") is True
    assert ctx.get_state("s3_ran") is True
    assert ctx.finished_at is not None
    assert ctx.total_duration_ms >= 0


@pytest.mark.asyncio
async def test_pipeline_stage_names():
    """Pipeline stage names should be correct."""
    stages = [SuccessStage("first"), SuccessStage("second")]
    pipeline = PipelineOrchestrator(stages)

    assert pipeline.stage_names == ["first", "second"]


@pytest.mark.asyncio
async def test_pipeline_failure_stops_on_error():
    """Pipeline should stop on first error by default."""
    stages = [SuccessStage("s1"), FailingStage("s2"), SuccessStage("s3")]
    pipeline = PipelineOrchestrator(stages)
    ctx = PipelineContext(query="test")

    from app.core.exceptions import PipelineFailedError

    with pytest.raises(PipelineFailedError) as exc_info:
        await pipeline.run(ctx)

    assert exc_info.value.stage == "s2"
    assert len(ctx.stage_results) == 2  # s1 ran, s2 failed, s3 didn't run
    assert ctx.stage_results[0].success is True
    assert ctx.stage_results[1].success is False
    assert ctx.stage_results[1].error == "Intentional test failure"
    assert ctx.get_state("s3_ran") is None  # s3 never ran


@pytest.mark.asyncio
async def test_pipeline_continue_on_error():
    """Pipeline with stop_on_error=False should continue after failure."""
    stages = [SuccessStage("s1"), FailingStage("s2"), SuccessStage("s3")]
    pipeline = PipelineOrchestrator(stages)
    ctx = PipelineContext(query="test")

    ctx = await pipeline.run(ctx, stop_on_error=False)

    assert len(ctx.stage_results) == 3
    assert ctx.stage_results[0].success is True
    assert ctx.stage_results[1].success is False
    assert ctx.stage_results[2].success is True
    assert ctx.success is False  # overall not successful
    assert ctx.failed_stage == "s2"


@pytest.mark.asyncio
async def test_pipeline_context_trace_id():
    """Pipeline context should have a trace ID."""
    ctx = PipelineContext(query="test")
    assert ctx.trace_id is not None
    assert len(ctx.trace_id) == 32  # 16 bytes hex = 32 chars


@pytest.mark.asyncio
async def test_pipeline_progress_callback():
    """Progress callback should be called after each stage."""
    stages = [SuccessStage("s1"), SuccessStage("s2"), SuccessStage("s3")]
    pipeline = PipelineOrchestrator(stages)
    ctx = PipelineContext(query="test")

    callbacks: list[tuple[str, int, int]] = []

    async def progress_cb(stage_name: str, idx: int, total: int, _ctx):
        callbacks.append((stage_name, idx, total))

    ctx = await pipeline.run(ctx, progress_callback=progress_cb)

    assert len(callbacks) == 3
    assert callbacks[0] == ("s1", 1, 3)
    assert callbacks[1] == ("s2", 2, 3)
    assert callbacks[2] == ("s3", 3, 3)


@pytest.mark.asyncio
async def test_pipeline_cancellation():
    """Cancelled pipeline should stop early."""
    stages = [SuccessStage("s1"), SlowStage("slow"), SuccessStage("s2")]
    pipeline = PipelineOrchestrator(stages)
    ctx = PipelineContext(query="test")

    # Cancel before the slow stage runs
    async def cancel_after_first(
        stage_name: str, idx: int, total: int, pctx: PipelineContext
    ):
        if idx == 1:  # after first stage
            pctx.cancel()

    ctx = await pipeline.run(ctx, progress_callback=cancel_after_first)

    assert ctx.cancelled is True
    # s1 completed, slow should not have started (cancelled before)
    # Actually the cancellation is checked before each stage, so s1 runs,
    # then cancelled, so slow and s2 don't run
    assert len(ctx.stage_results) == 1
    assert ctx.stage_results[0].stage_name == "s1"
