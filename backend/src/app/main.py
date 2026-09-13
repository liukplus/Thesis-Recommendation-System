"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.middleware import (
    CatMiddleware,
    RequestLoggingMiddleware,
    TraceIdMiddleware,
)
from app.api.v1.router import api_router
from app.config import get_settings
from app.core import cat_integration
from app.core.logging import get_logger, setup_logging
from app.db.session import dispose_db, init_db
from app.llm.factory import close_llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    settings = get_settings()

    # Startup
    setup_logging(settings.log_level)
    logger = get_logger(__name__)
    logger.info(f"Starting {settings.app_name} v{__version__} ({settings.app_env})")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # In dev, seed an empty database with the bundled demo catalog so the app
    # is explorable without external services. Never block startup on seeding.
    if settings.is_dev and settings.seed_demo_data:
        try:
            from app.db.seed import seed_demo_papers

            inserted = seed_demo_papers()
            if inserted:
                logger.info(f"Seeded {inserted} demo papers into an empty database")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Demo data seeding skipped: {e}")

    # Initialize CAT (Meituan APM)
    cat_integration.init(
        appkey=settings.cat_appkey,
        enabled=settings.cat_enabled,
        server_host=settings.cat_server_host,
        server_port=settings.cat_server_port,
    )
    cat_integration.log_event("App", "startup", data=f"env={settings.app_env}")

    yield

    # Shutdown
    cat_integration.log_event("App", "shutdown")
    logger.info("Shutting down...")
    dispose_db()
    await close_llm()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Thesis Recommendation System API",
        description="Intelligent Paper Search and Recommendation System with RAG + Agent",
        version=__version__,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware — order matters!
    app.add_middleware(RequestLoggingMiddleware)  # outermost: log everything
    app.add_middleware(CatMiddleware)             # CAT Transaction per request
    app.add_middleware(TraceIdMiddleware)         # innermost: trace ID first

    # Exception handlers
    register_exception_handlers(app)

    # API v1 router
    app.include_router(api_router)

    # Top-level health endpoints (for Kubernetes / load balancers)
    @app.get("/health/live", tags=["health"])
    async def health_live_top() -> dict:
        """Liveness probe."""
        return {"status": "ok", "service": settings.app_name}

    @app.get("/health/ready", tags=["health"])
    async def health_ready_top() -> dict:
        """Readiness probe."""
        return {"status": "ok", "service": settings.app_name}

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root() -> dict:
        """Root endpoint with API information."""
        return {
            "service": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "api_v1": "/api/v1",
            "health": "/api/v1/health/live",
        }

    return app


app = create_app()
