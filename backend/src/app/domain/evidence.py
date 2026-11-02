"""Evidence chunk — an extractive span that grounds the generated answer.

Honours D9: an evidence span is stored only when it verbatim-matches the source
text, so the default for ``verbatim`` is ``True`` (a derived span is never
stored). Maps to the ``EvidenceChunk`` table in the thesis (证据片段).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceChunk(BaseModel):
    """A single verbatim evidence span extracted from a paper."""

    chunk_id: str
    paper_id: str
    record_id: str | None = None
    section: str = "abstract"
    content: str
    anchor: str
    verbatim: bool = True
    reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
