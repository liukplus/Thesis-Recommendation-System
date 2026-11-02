"""PipelineData — the typed carrier for everything a pipeline run produces.

One field per stage output. This replaces the untyped ``data: dict`` that the
stages previously passed around by string key.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.contract import QueryContract
from app.domain.evidence import EvidenceChunk
from app.domain.export import Export
from app.domain.paper import Paper
from app.domain.record import SearchRecord
from app.domain.survey import Survey


class PipelineData(BaseModel):
    """Typed state shared by the eight pipeline stages."""

    # stage 1
    contract: QueryContract | None = None
    # stage 2
    recalled: list[Paper] = Field(default_factory=list)
    search_record: SearchRecord | None = None
    # stage 3
    fused: list[Paper] = Field(default_factory=list)
    # stage 4
    ranked: list[Paper] = Field(default_factory=list)
    # stage 5
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    # stage 6
    survey: Survey | None = None
    # stage 7
    verified: Survey | None = None
    # stage 8
    exports: Export | None = None
