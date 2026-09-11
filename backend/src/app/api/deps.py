"""FastAPI dependency injection.

Provides dependencies for getting settings, database sessions, LLM clients, etc.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_session as _get_db_session
from app.llm.base import LLMClient
from app.llm.factory import get_llm


def get_settings_dep() -> Settings:
    """FastAPI dependency: get application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def get_db() -> Session:
    """FastAPI dependency: get a database session.

    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    with _get_db_session() as session:
        yield session


DBSessionDep = Annotated[Session, Depends(get_db)]


def get_llm_client(settings: SettingsDep) -> Optional[LLMClient]:
    """FastAPI dependency: get the LLM client.

    Returns None if no API key is configured.
    """
    if not settings.llm_api_key:
        return None
    return get_llm(settings)


LLMClientDep = Annotated[Optional[LLMClient], Depends(get_llm_client)]


def get_trace_id_from_header(request: Request) -> Optional[str]:
    """FastAPI dependency: extract trace ID from request headers.

    Checks X-Trace-Id header.
    """
    return request.headers.get("x-trace-id")


TraceIdDep = Annotated[Optional[str], Depends(get_trace_id_from_header)]
