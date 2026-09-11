"""Guardrails for the agent loop.

Prevents the agent from:
- Running too many steps (step limit)
- Using too many tokens (budget limit)
- Getting stuck in loops (fingerprint detection)
- Repeating the same tool call (circuit breaker)

All guardrails are checked after each agent step.
If any guardrail is triggered, the agent stops with an appropriate reason.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GuardrailResult:
    """Result of a guardrail check.

    Attributes:
        should_stop: Whether the agent should stop.
        reason: Why the agent should stop (empty if should_stop is False).
        level: Severity level: info | warning | error.
    """

    should_stop: bool = False
    reason: str = ""
    level: str = "info"


class GuardrailController:
    """Manages and enforces agent guardrails.

    Checks are run after each agent step. Each check returns a GuardrailResult.
    If any check returns should_stop=True, the agent halts.

    Guardrails:
    1. Step limit: hard cap on number of steps
    2. Token budget: max total tokens
    3. Loop detection: same tool+args 3x in a row → circuit break
    4. Consecutive errors: 3 consecutive tool call errors → stop
    """

    def __init__(
        self,
        max_steps: int = 5,
        max_total_tokens: int = 0,
        loop_threshold: int = 3,
        max_consecutive_errors: int = 3,
    ) -> None:
        """Initialize guardrail controller.

        Args:
            max_steps: Maximum allowed steps (0 = unlimited).
            max_total_tokens: Maximum total tokens (0 = unlimited).
            loop_threshold: How many identical tool calls before breaking the loop.
            max_consecutive_errors: Max consecutive tool errors before stopping.
        """
        self.max_steps = max_steps
        self.max_total_tokens = max_total_tokens
        self.loop_threshold = loop_threshold
        self.max_consecutive_errors = max_consecutive_errors

        # Loop detection state
        self._fingerprints: list[str] = []  # recent tool call fingerprints
        self._consecutive_errors = 0
        self._tool_call_counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_all(self, state: Any) -> GuardrailResult:
        """Run all guardrail checks.

        Args:
            state: Current agent state.

        Returns:
            GuardrailResult with the first triggered check (most severe first).
        """
        checks = [
            self._check_step_limit,
            self._check_token_budget,
            self._check_loop_detection,
            self._check_consecutive_errors,
        ]

        for check_fn in checks:
            result = check_fn(state)
            if result.should_stop:
                logger.warning(
                    f"Guardrail triggered: {check_fn.__name__} — {result.reason}"
                )
                return result

        return GuardrailResult()

    def _check_step_limit(self, state: Any) -> GuardrailResult:
        """Check if step limit has been reached."""
        if self.max_steps <= 0:
            return GuardrailResult()

        if state.step_idx >= self.max_steps:
            return GuardrailResult(
                should_stop=True,
                reason=f"Reached maximum step limit ({self.max_steps})",
                level="warning",
            )
        return GuardrailResult()

    def _check_token_budget(self, state: Any) -> GuardrailResult:
        """Check if token budget has been exceeded."""
        if self.max_total_tokens <= 0:
            return GuardrailResult()

        if state.usage.total_tokens >= self.max_total_tokens:
            return GuardrailResult(
                should_stop=True,
                reason=f"Token budget exceeded: {state.usage.total_tokens} > {self.max_total_tokens}",
                level="error",
            )
        return GuardrailResult()

    def _check_loop_detection(self, state: Any) -> GuardrailResult:
        """Check if the agent is in a loop (same tool+args repeated)."""
        if len(self._fingerprints) < self.loop_threshold:
            return GuardrailResult()

        # Check if the last N fingerprints are identical
        recent = self._fingerprints[-self.loop_threshold:]
        if len(set(recent)) == 1:
            fingerprint = recent[0]
            return GuardrailResult(
                should_stop=True,
                reason=(
                    f"Detected loop: same tool call pattern '{fingerprint}' "
                    f"repeated {self.loop_threshold}x"
                ),
                level="warning",
            )
        return GuardrailResult()

    def _check_consecutive_errors(self, state: Any) -> GuardrailResult:
        """Check if there have been too many consecutive tool errors."""
        if self._consecutive_errors >= self.max_consecutive_errors:
            return GuardrailResult(
                should_stop=True,
                reason=(
                    f"Too many consecutive tool errors: {self._consecutive_errors} "
                    f"(max {self.max_consecutive_errors})"
                ),
                level="error",
            )
        return GuardrailResult()

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def record_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Record a tool call for loop detection.

        Args:
            tool_name: Name of the tool called.
            arguments: Tool arguments (used to compute fingerprint).
        """
        fingerprint = f"{tool_name}:{_fingerprint_args(arguments)}"
        self._fingerprints.append(fingerprint)
        self._tool_call_counts[tool_name] += 1

        # Keep only recent fingerprints (last 10) to limit memory
        if len(self._fingerprints) > 10:
            self._fingerprints = self._fingerprints[-10:]

    def record_tool_success(self) -> None:
        """Record a successful tool call (resets error counter)."""
        self._consecutive_errors = 0

    def record_tool_error(self) -> None:
        """Record a failed tool call (increments error counter)."""
        self._consecutive_errors += 1

    @property
    def total_tool_calls(self) -> int:
        """Total number of tool calls recorded."""
        return sum(self._tool_call_counts.values())

    def get_stats(self) -> dict[str, Any]:
        """Get guardrail statistics."""
        return {
            "max_steps": self.max_steps,
            "max_total_tokens": self.max_total_tokens,
            "loop_threshold": self.loop_threshold,
            "consecutive_errors": self._consecutive_errors,
            "total_tool_calls": self.total_tool_calls,
            "tool_call_breakdown": dict(self._tool_call_counts),
        }


def _fingerprint_args(arguments: dict[str, Any]) -> str:
    """Compute a deterministic fingerprint from tool arguments.

    Sorts keys and truncates long values to keep fingerprints manageable.
    """
    if not arguments:
        return "no_args"

    parts = []
    for key in sorted(arguments.keys()):
        val = str(arguments[key])
        if len(val) > 50:
            val = val[:47] + "..."
        parts.append(f"{key}={val}")
    return "|".join(parts)
