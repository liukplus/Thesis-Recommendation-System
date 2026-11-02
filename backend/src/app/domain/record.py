"""Search record — the log of a single multi-source recall.

Maps to the ``SearchRecord`` table in the thesis (查询记录). Written by stage 2.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SearchRecord(BaseModel):
    """A record of one recall pass: the query used and the papers it returned."""

    record_id: str
    query_text: str
    filters: dict = Field(default_factory=dict)
    result_paper_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
