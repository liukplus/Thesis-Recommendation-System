"""Survey and citations — the generated answer with pre-numbered references.

Honours D7: citations are pre-numbered ``[1..N]``. A ``Citation`` points back to
the evidence chunk it quotes, so stage 7 can verify both existence (L1) and
support (L2).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A single citation in the survey answer, pre-numbered by ``index``."""

    index: int
    paper_id: str
    chunk_id: str | None = None


class Survey(BaseModel):
    """The generated answer plus its numbered citations."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
