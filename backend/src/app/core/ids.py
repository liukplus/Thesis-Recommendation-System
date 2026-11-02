"""ID generation and trace context management."""
from __future__ import annotations

import secrets
import time
from contextvars import ContextVar

# Trace ID context variable - set per request/task
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_id(prefix: str) -> str:
    """Generate a new ID with a prefix.

    Format: {prefix}_{timestamp}_{random_hex}

    Args:
        prefix: Short identifier for the entity type (e.g., "paper", "task").

    Returns:
        A unique ID string.
    """
    timestamp = int(time.time() * 1000)
    random = secrets.token_hex(4)
    return f"{prefix}_{timestamp}_{random}"


def new_trace_id() -> str:
    """Generate a new trace ID (32 hex characters).

    Returns:
        A random 32-character hex string.
    """
    return secrets.token_hex(16)


def get_trace_id() -> str | None:
    """Get the trace ID for the current context.

    Returns:
        The current trace ID, or None if not set.
    """
    return _trace_id.get()


def set_trace_id(trace_id: str | None) -> None:
    """Set the trace ID for the current context.

    Args:
        trace_id: The trace ID to set, or None to clear.
    """
    _trace_id.set(trace_id)


def ensure_trace_id() -> str:
    """Get the current trace ID, creating one if it doesn't exist.

    Returns:
        The current (or newly created) trace ID.
    """
    tid = _trace_id.get()
    if tid is None:
        tid = new_trace_id()
        _trace_id.set(tid)
    return tid


def new_short_id(prefix: str = "") -> str:
    """Generate a short random ID (8 chars). Good for in-memory keys.

    Args:
        prefix: Optional prefix.

    Returns:
        Short ID string.
    """
    random = secrets.token_hex(4)
    return f"{prefix}_{random}" if prefix else random
