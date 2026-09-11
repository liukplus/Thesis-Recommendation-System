"""Health check endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app import __version__
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def health_live() -> HealthResponse:
    """Liveness probe — the service is running."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc),
        version=__version__,
    )


@router.get("/ready", response_model=HealthResponse)
async def health_ready() -> HealthResponse:
    """Readiness probe — the service is ready to serve requests.

    In production, check database and LLM connectivity here.
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc),
        version=__version__,
    )
