"""Pipeline orchestrator.

Runs stages sequentially on a PipelineContext.
Handles errors, timing, cancellation, and progress callbacks.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from app.core import cat_integration
from app.core.exceptions import PipelineFailedError
from app.core.logging import get_logger
from app.core.tracing import get_tracer
from app.pipeline.base import Stage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)

# Type alias for progress callback
# signature: (stage_name, stage_index, total_stages, ctx) -> None
ProgressCallback = Callable[[str, int, int, PipelineContext], Awaitable[None] | None]


class PipelineOrchestrator:
    """Runs a sequence of stages on a PipelineContext.

    Features:
    - Sequential stage execution
    - Error handling with partial results
    - Cancellation support
    - Progress callbacks
    - Tracing spans per stage (CAT Transactions when available)
    """

    def __init__(self, stages: list[Stage]) -> None:
        """Initialize the orchestrator.

        Args:
            stages: List of stages to run in order.
        """
        self._stages = list(stages)
        self._tracer = get_tracer()

    @property
    def stages(self) -> list[Stage]:
        """List of stages."""
        return list(self._stages)

    @property
    def stage_names(self) -> list[str]:
        """Names of all stages."""
        return [s.name for s in self._stages]

    async def run(
        self,
        ctx: PipelineContext,
        *,
        progress_callback: Optional[ProgressCallback] = None,
        stop_on_error: bool = True,
    ) -> PipelineContext:
        """Run all stages on the context.

        Args:
            ctx: The pipeline context to operate on.
            progress_callback: Optional async callback called after each stage.
            stop_on_error: If True (default), stop on first error.
                           If False, continue running remaining stages.

        Returns:
            The same PipelineContext, mutated with results.

        Raises:
            PipelineFailedError: If stop_on_error is True and a stage fails.
        """
        ctx.install_trace()
        total = len(self._stages)

        # CAT: log pipeline start
        cat_integration.log_event("Pipeline", "start", data=f"query={ctx.query[:60]}...")
        cat_integration.metric("pipeline.run").count()

        logger.info(f"Pipeline started: {total} stages, query={ctx.query[:60]}...")

        for i, stage in enumerate(self._stages):
            # Check for cancellation
            if ctx.cancelled:
                cat_integration.log_event("Pipeline", "cancelled", data=f"stage={stage.name}")
                logger.info(f"Pipeline cancelled at stage {i+1}/{total}: {stage.name}")
                break

            with self._tracer.span(f"pipeline.{stage.name}", stage_index=str(i)):
                try:
                    ctx = await stage.run(ctx)
                    logger.info(
                        f"Stage {i+1}/{total} [{stage.name}] "
                        f"completed ({ctx.stage_results[-1].duration_ms:.1f}ms)"
                    )
                except Exception as e:
                    logger.error(
                        f"Stage {i+1}/{total} [{stage.name}] failed: {e}"
                    )
                    cat_integration.log_event(
                        "Pipeline",
                        f"stage_failed:{stage.name}",
                        status=cat_integration.CAT_ERROR,
                        data=str(e),
                    )
                    if stop_on_error:
                        ctx.finish()
                        raise PipelineFailedError(
                            stage=stage.name,
                            message=f"Pipeline failed at stage '{stage.name}': {e}",
                        ) from e
                    # Continue with remaining stages
                    logger.warning(
                        f"Continuing pipeline despite error in stage '{stage.name}'"
                    )

            # Fire progress callback
            if progress_callback is not None:
                try:
                    result = progress_callback(stage.name, i + 1, total, ctx)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    # Don't let progress callback failures break the pipeline
                    logger.warning(f"Progress callback error: {e}")

        ctx.finish()
        status = "success" if ctx.success else "partial_failure"

        # CAT: log pipeline end
        cat_integration.log_event(
            "Pipeline",
            status,
            data=f"stages={len(ctx.stage_results)}/{total}, duration={ctx.total_duration_ms:.0f}ms",
        )
        cat_integration.metric("pipeline.duration").duration(ctx.total_duration_ms)

        logger.info(
            f"Pipeline {status}: {ctx.total_duration_ms:.1f}ms, "
            f"{len(ctx.stage_results)}/{total} stages completed"
        )

        return ctx

    async def run_stage(
        self,
        ctx: PipelineContext,
        stage_name: str,
    ) -> PipelineContext:
        """Run a single specific stage by name.

        Args:
            ctx: Pipeline context.
            stage_name: Name of the stage to run.

        Returns:
            The context after running the stage.

        Raises:
            ValueError: If the stage name is not found.
        """
        stage = next((s for s in self._stages if s.name == stage_name), None)
        if stage is None:
            raise ValueError(f"Unknown stage: {stage_name}")

        ctx.install_trace()
        cat_integration.log_event("Pipeline", f"single_stage:{stage_name}")
        with self._tracer.span(f"pipeline.{stage_name}", mode="single"):
            ctx = await stage.run(ctx)

        return ctx


def create_default_pipeline() -> PipelineOrchestrator:
    """Create the default 8-stage pipeline.

    Returns:
        PipelineOrchestrator with all 8 stages in order.
    """
    from app.pipeline.stages.stage1_query import QueryParseStage
    from app.pipeline.stages.stage2_recall import RecallStage
    from app.pipeline.stages.stage3_fusion import FusionStage
    from app.pipeline.stages.stage4_rerank import RerankStage
    from app.pipeline.stages.stage5_evidence import EvidenceExtractionStage
    from app.pipeline.stages.stage6_survey import SurveyGenerationStage
    from app.pipeline.stages.stage7_verify import CitationVerificationStage
    from app.pipeline.stages.stage8_export import ExportStage

    stages = [
        QueryParseStage(),
        RecallStage(),
        FusionStage(),
        RerankStage(),
        EvidenceExtractionStage(),
        SurveyGenerationStage(),
        CitationVerificationStage(),
        ExportStage(),
    ]
    return PipelineOrchestrator(stages)
