"""FastAPI middleware.

- Trace ID middleware: extract/generate trace IDs and inject into logging context.
- Request logging middleware: log all requests with timing.
- CAT middleware: wrap each HTTP request in a CAT Transaction for APM monitoring.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import cat_integration
from app.core.ids import ensure_trace_id, set_trace_id
from app.core.logging import get_logger

logger = get_logger(__name__)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Middleware that sets up trace ID for each request.

    Reads X-Trace-Id header if present, otherwise generates a new one.
    Adds the trace ID to the response headers and logging context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or create trace ID
        trace_id = request.headers.get("x-trace-id") or ensure_trace_id()
        set_trace_id(trace_id)

        # Process request
        response = await call_next(request)

        # Add trace ID to response headers
        response.headers["X-Trace-Id"] = trace_id

        # Clear trace ID from context
        set_trace_id(None)

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all HTTP requests with timing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        method = request.method
        path = request.url.path

        logger.info(f"Request started: {method} {path}")

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            status_code = response.status_code

            logger.info(
                f"Request completed: {method} {path} -> {status_code} ({duration_ms:.1f}ms)"
            )
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {method} {path} -> {type(e).__name__}: {e} ({duration_ms:.1f}ms)"
            )
            raise


class CatMiddleware(BaseHTTPMiddleware):
    """Middleware that wraps each HTTP request in a CAT Transaction.

    Creates a CAT Transaction for every request with:
    - Type: "HTTP"
    - Name: "{method} {path}"
    - Data: status code, duration, query params
    - Status: based on HTTP status code (4xx/5xx → error)

    This middleware should be placed AFTER TraceIdMiddleware so the trace
    ID is available in the logging context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method
        path = request.url.path

        # Skip health check endpoints to reduce noise
        if path in ("/health/live", "/health/ready", "/"):
            return await call_next(request)

        with cat_integration.transaction(
            "HTTP",
            f"{method} {path}",
            method=method,
            path=path,
        ) as t:
            try:
                response = await call_next(request)
                status_code = response.status_code

                if t:
                    t.add_data(f"status={status_code}")
                    if status_code >= 500:
                        t.set_status(cat_integration.CAT_ERROR)
                    elif status_code >= 400:
                        t.set_status("warning")

                # Log 4xx/5xx as CAT Events for alerting
                if status_code >= 500:
                    cat_integration.log_event(
                        "HTTP",
                        f"{status_code} {method} {path}",
                        status=cat_integration.CAT_ERROR,
                        data=f"status={status_code}",
                    )
                elif status_code >= 400:
                    cat_integration.log_event(
                        "HTTP",
                        f"{status_code} {method} {path}",
                        status="warning",
                    )

                return response
            except Exception as e:
                if t:
                    t.set_status(cat_integration.CAT_ERROR)
                    t.add_data(f"error={e}")
                cat_integration.log_exception(e)
                raise
