"""Logging configuration with trace ID injection and CAT integration."""
from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.core.ids import get_trace_id


class TraceIdFilter(logging.Filter):
    """Log filter that adds the current trace ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "no-trace"
        return True


class CatLogHandler(logging.Handler):
    """Log handler that sends ERROR/WARNING records to CAT as Events.

    Integrates Python logging with CAT (Meituan APM) so that:
    - ERROR logs → CAT Events with status=error (or CAT Exception if exc_info is set)
    - WARNING logs → CAT Events with status=warning
    - INFO/DEBUG are not forwarded to CAT (too noisy)

    This handler is a no-op if the CAT client is not initialized.
    """

    def __init__(self, level: int = logging.WARNING) -> None:
        super().__init__(level=level)

    def emit(self, record: logging.LogRecord) -> None:
        """Send a log record to CAT."""
        try:
            # Avoid circular import
            from app.core import cat_integration

            if not cat_integration.is_available():
                return

            msg = self.format(record)
            logger_name = record.name

            if record.exc_info and record.exc_info[0]:
                # Log with full exception info
                exc = record.exc_info[1]
                cat_integration.log_exception(
                    exc,
                    trace_info=msg,
                )
            elif record.levelno >= logging.ERROR:
                cat_integration.log_event(
                    "Log",
                    f"ERROR:{logger_name}",
                    status=cat_integration.CAT_ERROR,
                    data=msg[:200],
                )
            elif record.levelno >= logging.WARNING:
                cat_integration.log_event(
                    "Log",
                    f"WARNING:{logger_name}",
                    status="warning",
                    data=msg[:200],
                )
        except Exception:
            # Don't let logging exceptions crash the app
            pass


def setup_logging(level: str = "info") -> None:
    """Configure root logger with JSON formatting, trace IDs, and CAT integration.

    Args:
        level: Log level name (debug, info, warning, error).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(trace_id)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
    )
    handler.setFormatter(formatter)
    handler.addFilter(TraceIdFilter())

    root_logger.addHandler(handler)

    # CAT handler: sends ERROR/WARNING to CAT as Events
    cat_handler = CatLogHandler(level=logging.WARNING)
    cat_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(cat_handler)

    # Lower noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger.

    Convenience function so callers don't need to import logging directly.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
