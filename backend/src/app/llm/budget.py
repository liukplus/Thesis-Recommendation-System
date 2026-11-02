"""Token budget tracking for LLM calls.

Tracks tokens spent and enforces limits per request/session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import AuthorizationError
from app.llm.base import Usage


@dataclass
class TokenBudget:
    """Tracks token usage and enforces budget limits.

    Attributes:
        max_prompt_tokens: Maximum allowed prompt tokens (0 = unlimited).
        max_completion_tokens: Maximum allowed completion tokens (0 = unlimited).
        max_total_tokens: Maximum allowed total tokens (0 = unlimited).
    """

    max_prompt_tokens: int = 0
    max_completion_tokens: int = 0
    max_total_tokens: int = 0

    _prompt_used: int = 0
    _completion_used: int = 0
    _total_used: int = 0
    _history: list[Usage] = field(default_factory=list)

    def record(self, usage: Usage) -> None:
        """Record token usage from a call.

        Args:
            usage: Usage statistics from the LLM call.

        Raises:
            BudgetExceededError: If recording would exceed the budget.
        """
        new_prompt = self._prompt_used + usage.prompt_tokens
        new_completion = self._completion_used + usage.completion_tokens
        new_total = self._total_used + usage.total_tokens

        if self.max_prompt_tokens and new_prompt > self.max_prompt_tokens:
            raise BudgetExceededError(
                f"Prompt token budget exceeded: {new_prompt} > {self.max_prompt_tokens}",
                budget_type="prompt",
                used=new_prompt,
                limit=self.max_prompt_tokens,
            )
        if self.max_completion_tokens and new_completion > self.max_completion_tokens:
            raise BudgetExceededError(
                f"Completion token budget exceeded: {new_completion} > {self.max_completion_tokens}",
                budget_type="completion",
                used=new_completion,
                limit=self.max_completion_tokens,
            )
        if self.max_total_tokens and new_total > self.max_total_tokens:
            raise BudgetExceededError(
                f"Total token budget exceeded: {new_total} > {self.max_total_tokens}",
                budget_type="total",
                used=new_total,
                limit=self.max_total_tokens,
            )

        self._prompt_used = new_prompt
        self._completion_used = new_completion
        self._total_used = new_total
        self._history.append(usage)

    @property
    def prompt_used(self) -> int:
        """Total prompt tokens used."""
        return self._prompt_used

    @property
    def completion_used(self) -> int:
        """Total completion tokens used."""
        return self._completion_used

    @property
    def total_used(self) -> int:
        """Total tokens used."""
        return self._total_used

    @property
    def remaining_total(self) -> int:
        """Remaining total token budget (0 if unlimited)."""
        if not self.max_total_tokens:
            return 0
        return max(0, self.max_total_tokens - self._total_used)

    @property
    def usage(self) -> Usage:
        """Current cumulative usage."""
        return Usage(
            prompt_tokens=self._prompt_used,
            completion_tokens=self._completion_used,
            total_tokens=self._total_used,
        )

    def check_completion_budget(self, estimated: int) -> bool:
        """Check if estimated completion tokens fit in the budget.

        Args:
            estimated: Estimated tokens needed for the next call.

        Returns:
            True if within budget, False otherwise.
        """
        completion_exceeded = (
            self.max_completion_tokens
            and self._completion_used + estimated > self.max_completion_tokens
        )
        total_exceeded = (
            self.max_total_tokens and self._total_used + estimated > self.max_total_tokens
        )
        return not completion_exceeded and not total_exceeded

    def reset(self) -> None:
        """Reset the budget counters."""
        self._prompt_used = 0
        self._completion_used = 0
        self._total_used = 0
        self._history.clear()


class BudgetExceededError(AuthorizationError):
    """Raised when a token budget is exceeded."""

    code = "budget_exceeded"

    def __init__(
        self,
        message: str,
        *,
        budget_type: str,
        used: int,
        limit: int,
    ) -> None:
        super().__init__(
            message,
            details={
                "budget_type": budget_type,
                "used": used,
                "limit": limit,
            },
        )
        self.budget_type = budget_type
        self.used = used
        self.limit = limit
