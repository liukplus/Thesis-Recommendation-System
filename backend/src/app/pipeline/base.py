"""Base stage protocol and abstract implementations.

All pipeline stages implement the Stage protocol:
- `name: str` — short name of the stage
- `async run(ctx: PipelineContext) -> PipelineContext` — execute the stage
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from app.pipeline.context import PipelineContext, StageResult


@runtime_checkable
class Stage(Protocol):
    """Protocol that all pipeline stages must implement."""

    @property
    def name(self) -> str:
        """Short name of the stage (e.g., 'query_parse')."""
        ...

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Execute the stage, mutating and returning the context.

        Args:
            ctx: Pipeline context with state from previous stages.

        Returns:
            The same context object, mutated with this stage's results.
        """
        ...


class BaseStage(ABC):
    """Abstract base class for pipeline stages.

    Provides common boilerplate: timing, error handling, result recording.
    Subclasses implement `_execute()` instead of `run()`.
    """

    def __init__(self, name: str | None = None) -> None:
        """Initialize the stage.

        Args:
            name: Stage name. Defaults to the class name converted to snake_case.
        """
        if name:
            self._name = name
        else:
            # Convert ClassName to class_name
            self._name = _camel_to_snake(self.__class__.__name__)

    @property
    def name(self) -> str:
        """Stage name."""
        return self._name

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        """Run the stage with timing and error handling.

        Don't override this — override `_execute()` instead.
        """
        result = StageResult(stage_name=self.name)
        ctx.current_stage = self.name
        ctx.add_result(result)

        try:
            await self._execute(ctx)
            result.finish(success=True)
        except Exception as e:
            result.finish(success=False, error=str(e))
            raise
        finally:
            ctx.current_stage = None

        return ctx

    @abstractmethod
    async def _execute(self, ctx: PipelineContext) -> None:
        """Execute the stage logic.

        Implement this in subclasses. Read from ctx.state, write to ctx.state.
        Raise exceptions on failure — they'll be caught and recorded.

        Args:
            ctx: Pipeline context.
        """
        ...


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)
