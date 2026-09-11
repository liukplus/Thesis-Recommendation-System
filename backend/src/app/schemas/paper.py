"""Schemas for paper-related API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaperBase(BaseModel):
    """Base paper fields shared by create/update."""

    title: str = Field(..., min_length=1, max_length=512)
    abstract: Optional[str] = None
    authors: Optional[str] = Field(default=None, max_length=512)
    doi: Optional[str] = Field(default=None, max_length=256)
    venue: Optional[str] = Field(default=None, max_length=256)
    year: Optional[int] = None
    url: Optional[str] = Field(default=None, max_length=1024)
    pdf_url: Optional[str] = Field(default=None, max_length=1024)


class PaperCreate(PaperBase):
    """Request to create a new paper."""

    pass


class PaperUpdate(BaseModel):
    """Request to update a paper (all fields optional)."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    abstract: Optional[str] = None
    authors: Optional[str] = Field(default=None, max_length=512)
    doi: Optional[str] = Field(default=None, max_length=256)
    venue: Optional[str] = Field(default=None, max_length=256)
    year: Optional[int] = None
    url: Optional[str] = Field(default=None, max_length=1024)
    pdf_url: Optional[str] = Field(default=None, max_length=1024)


class PaperResponse(PaperBase):
    """Response model for a paper."""

    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaperSearchQuery(BaseModel):
    """Paper search query parameters."""

    q: str = Field(..., min_length=1, max_length=500, description="Search query")
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class PaperSearchResponse(BaseModel):
    """Paper search results."""

    papers: list[PaperResponse]
    total: int
    query: str
