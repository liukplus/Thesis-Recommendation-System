"""Typed domain contracts for the thesis recommendation system.

Pure Pydantic models — safe to import from anywhere (no eager SDK/CAT/runtime
dependencies). These are the shared vocabulary of the pipeline stages and the
agent, replacing the untyped ``dict`` state that previously flowed between them.
"""
from __future__ import annotations

from app.domain.contract import Intent, QueryContract
from app.domain.evidence import EvidenceChunk
from app.domain.export import Export
from app.domain.paper import Paper, paper_to_wire
from app.domain.pipeline import PipelineData
from app.domain.record import SearchRecord
from app.domain.survey import Citation, Survey

__all__ = [
    "Citation",
    "EvidenceChunk",
    "Export",
    "Intent",
    "Paper",
    "PipelineData",
    "QueryContract",
    "SearchRecord",
    "Survey",
    "paper_to_wire",
]
