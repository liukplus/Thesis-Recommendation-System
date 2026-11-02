"""Paper — the typed paper record threaded through the pipeline.

This is the domain model; it is intentionally distinct from the ORM model in
``db/models/paper.py`` and the API schema in ``schemas/paper.py``. Those three
representations are reconciled in a later persistence pass.

``score``/``fused_score``/``rerank_score``/``rank`` are per-run retrieval
metadata written by the recall/fusion/rerank stages and are ``None`` until set.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Paper(BaseModel):
    """A single academic paper, as it flows through the RAG pipeline."""

    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    abstract: str = ""
    source: str = ""
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    citation_count: int = 0
    updated_at: datetime | None = None

    # Per-run retrieval metadata (populated by stages 2-4).
    score: float | None = None  # recall relevance
    fused_score: float | None = None  # RRF fused score
    rerank_score: float | None = None  # final rerank score
    rank: int | None = None  # position in the final ranked list


def paper_to_wire(paper: Paper) -> dict[str, Any]:
    """Map a ``Paper`` to the wire dict the frontend ``Paper`` type expects.

    The frontend reads ``id`` (not ``paper_id``) and a comma-joined ``authors``
    string, so this is where the domain -> API boundary mapping happens.
    """
    return {
        "id": paper.paper_id,
        "title": paper.title,
        "abstract": paper.abstract or None,
        "authors": ", ".join(paper.authors) if paper.authors else None,
        "doi": paper.doi,
        "venue": paper.venue,
        "year": paper.year,
        "url": paper.url,
        "pdf_url": paper.pdf_url,
        "score": paper.score,
        "rerank_score": paper.rerank_score,
        "rank": paper.rank,
    }
