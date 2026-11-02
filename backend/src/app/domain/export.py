"""Export — the final result rendered into multiple formats."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Export(BaseModel):
    """Rendered output keyed by format name (``markdown``/``bibtex``/``json``)."""

    formats: dict[str, str] = Field(default_factory=dict)
