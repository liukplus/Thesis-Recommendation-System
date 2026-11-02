"""Agent state management.

The AgentState object holds all mutable state for an agent run:
goal, messages, plan, step count, token usage, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.ids import new_id, new_trace_id
from app.llm.base import ChatMessage, Usage


@dataclass
class ToolCall:
    """A single tool call from the agent."""

    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None

    @property
    def duration_ms(self) -> float:
        """Duration of the tool call in milliseconds."""
        end = self.finished_at or datetime.utcnow()
        return (end - self.started_at).total_seconds() * 1000


@dataclass
class PlanStep:
    """A single step in the agent's plan."""

    index: int
    description: str
    status: str = "pending"  # pending | in_progress | completed | failed
    tool: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "status": self.status,
            "tool": self.tool,
        }


@dataclass
class AgentState:
    """Mutable state for an agent run.

    Attributes:
        task_id: Unique identifier for this agent task.
        goal: The user's original goal/query.
        step_idx: Current step number (0-indexed).
        messages: Full conversation history (for LLM).
        tool_calls: List of all tool calls made during this run.
        plan: Optional plan steps (for plan-first mode).
        plan_text: Raw plan text from the planner.
        usage: Cumulative token usage.
        trace_id: Trace ID for logging/tracing.
        started_at: When the agent run started.
        finished_at: When the agent run finished.
        status: Current status (running | completed | failed | cancelled).
        final_answer: The final answer text, if completed.
        error: Error message if failed.
        max_steps: Maximum allowed steps (hard cap).
        stop_reason: Why the agent stopped.
    """

    goal: str
    task_id: str = field(default_factory=lambda: new_id("agent"))
    step_idx: int = 0
    messages: list[ChatMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    plan: list[PlanStep] = field(default_factory=list)
    plan_text: str = ""
    usage: Usage = field(default_factory=Usage)
    trace_id: str = field(default_factory=new_trace_id)
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    status: str = "pending"  # pending | running | completed | failed | cancelled
    final_answer: str = ""
    error: str | None = None
    max_steps: int = 5
    stop_reason: str = ""

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    @property
    def is_finished(self) -> bool:
        """Whether the agent run has finished (completed/failed/cancelled)."""
        return self.status in ("completed", "failed", "cancelled")

    @property
    def total_tokens(self) -> int:
        """Total tokens used so far."""
        return self.usage.total_tokens

    @property
    def steps_taken(self) -> int:
        """Number of steps taken."""
        return self.step_idx

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call to the history."""
        self.tool_calls.append(tool_call)

    def add_usage(self, usage: Usage) -> None:
        """Add token usage to the running total."""
        self.usage.add(usage)

    def mark_completed(self, answer: str) -> None:
        """Mark the agent run as successfully completed."""
        self.status = "completed"
        self.final_answer = answer
        self.finished_at = datetime.utcnow()
        self.stop_reason = "completed"

    def mark_failed(self, error: str) -> None:
        """Mark the agent run as failed."""
        self.status = "failed"
        self.error = error
        self.finished_at = datetime.utcnow()
        self.stop_reason = "error"

    def mark_cancelled(self) -> None:
        """Mark the agent run as cancelled."""
        self.status = "cancelled"
        self.finished_at = datetime.utcnow()
        self.stop_reason = "cancelled"

    def increment_step(self) -> None:
        """Increment the step counter."""
        self.step_idx += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to a dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status,
            "step_idx": self.step_idx,
            "max_steps": self.max_steps,
            "trace_id": self.trace_id,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "plan": [s.to_dict() for s in self.plan],
            "tool_calls": [
                {
                    "call_id": tc.call_id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "error": tc.error,
                    "duration_ms": round(tc.duration_ms, 2),
                }
                for tc in self.tool_calls
            ],
            "final_answer": self.final_answer,
            "error": self.error,
            "stop_reason": self.stop_reason,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": round(
                (self.finished_at - self.started_at).total_seconds() * 1000
                if self.finished_at
                else (datetime.utcnow() - self.started_at).total_seconds() * 1000,
                2,
            ),
        }
