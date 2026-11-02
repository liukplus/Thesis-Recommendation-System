"""Query contract — the typed, structured form of a user query.

Stage 1 (query parsing) turns the raw user query into a ``QueryContract`` that
every downstream stage reads from, replacing the previous untyped
``parsed_query`` dict.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Intent(StrEnum):
    """The user's retrieval intent. Values match ``stage1._classify_intent``."""

    SURVEY = "survey"
    COMPARE = "compare"
    FIND_METHOD = "find_method"
    EXPLAIN = "explain"
    FIND_PAPER = "find_paper"


class QueryContract(BaseModel):
    """Structured query parameters shared by every stage in a pipeline run."""

    topic: str
    methods: list[str] = Field(default_factory=list)
    venue: str | None = None
    year_start: int | None = None
    year_end: int | None = None
    exclusions: list[str] = Field(default_factory=list)
    intent: Intent = Intent.FIND_PAPER
