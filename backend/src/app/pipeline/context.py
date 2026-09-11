"""Pipeline context - the single mutable object passed through all stages.

Every stage reads from and writes to this context.
This follows the "pipes and filters" architectural pattern.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.core.ids import new_trace_id, set_trace_id
from app.llm.budget import TokenBudget


@dataclass
class StageResult:
    """Result from a single pipeline stage."""

    stage_name: str
    success: bool = True
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    duration_ms: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def finish(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark this stage result as finished."""
        self.finished_at = datetime.utcnow()
        self.duration_ms = (self.finished_at - self.started_at).total_seconds() * 1000
        self.success = success
        self.error = error


@dataclass
class PipelineContext:
    """Context object passed through all pipeline stages.

    This is the single mutable state object for the entire pipeline run.
    Stages communicate by reading from and writing to `state`.

    Attributes:
        query: The original user query.
        trace_id: Trace ID for logging/tracing.
        state: Shared state dictionary for inter-stage communication.
        stage_results: Ordered list of stage results.
        budget: Token budget for this pipeline run.
        started_at: When the pipeline started.
        finished_at: When the pipeline finished (None if still running).
        cancelled: Whether the pipeline was cancelled.
        current_stage: Name of the currently running stage.
    """

    query: str
    trace_id: str = field(default_factory=new_trace_id)
    state: dict[str, Any] = field(default_factory=dict)
    stage_results: list[StageResult] = field(default_factory=list)
    budget: TokenBudget = field(default_factory=TokenBudget)
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    cancelled: bool = False
    current_stage: Optional[str] = None

    @property
    def total_duration_ms(self) -> float:
        """Total pipeline duration in milliseconds."""
        end = self.finished_at or datetime.utcnow()
        return (end - self.started_at).total_seconds() * 1000

    @property
    def success(self) -> bool:
        """Whether all completed stages succeeded."""
        if not self.stage_results:
            return False
        return all(r.success for r in self.stage_results)

    @property
    def failed_stage(self) -> Optional[str]:
        """Name of the first failed stage, if any."""
        for r in self.stage_results:
            if not r.success:
                return r.stage_name
        return None

    def get_result(self, stage_name: str) -> Optional[StageResult]:
        """Get the result for a specific stage.

        Args:
            stage_name: Name of the stage.

        Returns:
            The StageResult if the stage has run, None otherwise.
        """
        for r in self.stage_results:
            if r.stage_name == stage_name:
                return r
        return None

    def add_result(self, result: StageResult) -> None:
        """Add a stage result to the context."""
        self.stage_results.append(result)

    def set_state(self, key: str, value: Any) -> None:
        """Set a value in the shared state.

        Args:
            key: State key.
            value: State value.
        """
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a value from the shared state.

        Args:
            key: State key.
            default: Default value if key not found.

        Returns:
            The value, or default if not found.
        """
        return self.state.get(key, default)

    def cancel(self) -> None:
        """Cancel the pipeline run."""
        self.cancelled = True

    def finish(self) -> None:
        """Mark the pipeline as finished."""
        self.finished_at = datetime.utcnow()

    def install_trace(self) -> None:
        """Install the context's trace_id into the current context var.

        Call this at the start of processing in a new async context
        to ensure trace ID propagates through logging.
        """
        set_trace_id(self.trace_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize context to a dictionary for API responses."""
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "success": self.success,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "cancelled": self.cancelled,
            "failed_stage": self.failed_stage,
            "state": {
                k: v for k, v in self.state.items()
                if not k.startswith("_")  # hide internal state
            },
            "stages": [
                {
                    "name": r.stage_name,
                    "success": r.success,
                    "duration_ms": round(r.duration_ms, 2),
                    "error": r.error,
                }
                for r in self.stage_results
            ],
        }
