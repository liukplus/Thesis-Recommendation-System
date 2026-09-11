"""Tracing utilities with CAT (Meituan APM) backend.

For development without CAT, falls back to console-based tracing.
In Docker with CAT server, uses CAT Transactions for distributed tracing.

Usage:
    with get_tracer().span("operation", key="value") as span:
        do_work()

The span() context manager creates a CAT Transaction when CAT is available,
or a console-based Span as fallback.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from app.core import cat_integration
from app.core.ids import get_trace_id
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Span:
    """A simple span for timing and tracking operations.

    When CAT is available, this is a thin wrapper around a CAT Transaction.
    When CAT is unavailable, this is a standalone timing dataclass.
    """

    name: str
    trace_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    attributes: dict[str, str] = field(default_factory=dict)
    status: str = "ok"  # ok | error
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Duration of the span in milliseconds."""
        if self.end_time == 0.0:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def set_attribute(self, key: str, value: str) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def record_error(self, message: str) -> None:
        """Record an error on the span."""
        self.status = "error"
        self.error_message = message


class Tracer:
    """Tracer that uses CAT Transactions when available.

    If CAT is not available, falls back to console-based tracing.
    The API is identical in both cases.
    """

    def __init__(self, service_name: str = "thesis-recsys") -> None:
        self.service_name = service_name

    @contextmanager
    def span(self, name: str, **attributes: str):
        """Create a span context manager.

        When CAT is available, this creates a CAT Transaction.
        When CAT is unavailable, this creates a console-based Span.

        Usage:
            with tracer.span("my_operation", key="value"):
                do_work()
        """
        if cat_integration.is_available():
            # Use CAT Transaction as backend
            with cat_integration.transaction("Trace", name, **attributes) as t:
                try:
                    yield Span(name=name, trace_id=get_trace_id() or "")
                except Exception as e:
                    if t:
                        t.set_status(cat_integration.CAT_ERROR)
                        t.add_data(f"error={e}")
                    raise
        else:
            # Fallback: console-based span
            s = Span(
                name=name,
                trace_id=get_trace_id() or "no-trace",
                attributes=attributes,
            )
            s.start_time = time.time()
            logger.debug(f"span.start: {name}", extra={"span": name})

            try:
                yield s
            except Exception as e:
                s.record_error(str(e))
                raise
            finally:
                s.end_time = time.time()
                logger.debug(
                    f"span.end: {name} ({s.duration_ms:.1f}ms, {s.status})",
                    extra={
                        "span": name,
                        "duration_ms": s.duration_ms,
                        "status": s.status,
                    },
                )


# Global tracer instance
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def set_tracer(tracer: Tracer) -> None:
    """Set the global tracer instance (for testing)."""
    global _tracer
    _tracer = tracer
