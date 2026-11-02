"""CAT (Central Application Tracking) integration.

CAT is Meituan-Dianping's open-source distributed real-time application monitoring
platform. This module wraps the native cat-sdk Python client with a no-op fallback
for platforms where the native client is unavailable (Windows).

Usage:
    from app.core import cat_integration as cat

    # Initialize at startup
    cat.init("thesis-recsys")

    # Wrap a code block in a Transaction
    with cat.transaction("Service", "process"):
        do_work()

    # Log an event
    cat.log_event("Business", "order_placed")

    # Log an exception
    try:
        risky_operation()
    except Exception as e:
        cat.log_exception(e)

    # Record a metric
    cat.metric("api.requests").count()
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Try to import the native cat-sdk (Linux/Darwin only)
# ---------------------------------------------------------------------------
_HAS_NATIVE_CAT: bool = False
_native_cat: Any = None
_initialized: bool = False

try:
    import cat as _cat_module

    _native_cat = _cat_module
    _HAS_NATIVE_CAT = True
except (ImportError, RuntimeError) as e:
    logger.info(
        "Native CAT client not available (%s). "
        "Running in no-op fallback mode. CAT data will not be reported.",
        e,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CAT_SUCCESS: str = "0"
CAT_ERROR: str = "error"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def init(
    appkey: str,
    enabled: bool = True,
    server_host: str | None = None,
    server_port: int | None = None,
    **kwargs: Any,
) -> bool:
    """Initialize the CAT client.

    Must be called once at application startup.
    If CAT is disabled or the native client is unavailable, this is a no-op.

    Args:
        appkey: Application key (a-zA-Z0-9_- only).
        enabled: Whether CAT is enabled. Set to False to disable CAT entirely.
        server_host: CAT server hostname (overrides client.xml).
        server_port: CAT server TCP port (default 2280).
        **kwargs: Additional arguments passed to cat.init().

    Returns:
        True if CAT was initialized successfully, False otherwise.
    """
    global _initialized

    if not enabled:
        logger.info("CAT is disabled (CAT_ENABLED=false)")
        _initialized = False
        return False

    if not _HAS_NATIVE_CAT:
        logger.info("CAT: native client unavailable, running in fallback mode")
        _initialized = False
        return False

    try:
        # For cat-sdk, the server address is configured via
        # /data/appdatas/cat/client.xml, not through init() arguments.
        # The client.xml is mounted into the container by Docker Compose.
        _native_cat.init(appkey, **kwargs)
        _initialized = True
        logger.info(
            "CAT initialized: appkey=%s, server_host=%s, server_port=%s",
            appkey,
            server_host or "(from client.xml)",
            server_port or 2280,
        )
        return True
    except Exception as e:
        _initialized = False
        logger.warning("CAT initialization failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------
@contextmanager
def transaction(
    t_type: str,
    t_name: str,
    **data: str,
):
    """Create a CAT Transaction context manager.

    A Transaction tracks the execution time and status of a code block.
    It is automatically completed when the context manager exits.

    Usage:
        with cat.transaction("Service", "process_data", key="value") as t:
            result = do_work()
            if t:
                t.add_data(f"result={result}")
    """
    if not _initialized:
        yield None
        return

    t = _native_cat.Transaction(t_type, t_name)
    try:
        # Add data attributes
        for k, v in data.items():
            with suppress(Exception):
                t.add_data(f"{k}={v}")

        yield t
    except Exception as e:
        with suppress(Exception):
            t.set_status(CAT_ERROR)
            t.add_data(f"error={e}")
        raise
    finally:
        with suppress(Exception):
            t.complete()


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------
def log_event(
    e_type: str,
    e_name: str,
    status: str = "0",
    data: str = "",
) -> None:
    """Log a CAT Event.

    Events are one-time occurrences with no timing information.
    They appear in the CAT dashboard's Event report.

    Args:
        e_type: Event type (e.g., "Log", "Business", "System").
        e_name: Event name (e.g., "request_completed").
        status: "0" for success, "error" for failure.
        data: Additional event data string.
    """
    if not _initialized:
        return
    with suppress(Exception):
        _native_cat.log_event(e_type, e_name, status, data)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------
def log_exception(
    exception: BaseException,
    trace_info: str | None = None,
) -> None:
    """Log an exception to CAT.

    CAT Exception is a special Event with type="Exception" and
    name=exception.__class__.__name__. It automatically captures
    the stack trace.

    Args:
        exception: The exception to log (BaseException so logging's
            ``exc_info`` values, including SystemExit/KeyboardInterrupt, type-check).
        trace_info: Optional custom stack trace string.
    """
    if not _initialized:
        return
    with suppress(Exception):
        _native_cat.log_exception(exception, trace_info or "")


# ---------------------------------------------------------------------------
# Metric
# ---------------------------------------------------------------------------
class _NullMetric:
    """No-op metric for when CAT is unavailable."""

    def count(self, n: int = 1) -> None:
        """Increment the metric counter (no-op)."""
        pass

    def duration(self, ms: float) -> None:
        """Record a duration value (no-op)."""
        pass


def metric(name: str):
    """Get a CAT Metric counter.

    Metrics are aggregated by the CAT server every second.
    Counts are summed, durations are averaged.

    Usage:
        cat.metric("api.requests").count()
        cat.metric("api.latency").duration(150.0)
    """
    if not _initialized:
        return _NullMetric()
    with suppress(Exception):
        return _native_cat.metric(name)
    return _NullMetric()


# ---------------------------------------------------------------------------
# Convenience: status checking
# ---------------------------------------------------------------------------
def is_available() -> bool:
    """Check whether the native CAT client is initialized and ready."""
    return _initialized
