"""API v1 root router.

Aggregates all v1 endpoint routers.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import agent_routes, health, papers, pipeline_routes

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(pipeline_routes.router)
api_router.include_router(agent_routes.router)
api_router.include_router(papers.router)
