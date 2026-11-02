"""Paper model.

Slimmed-down version for the skeleton.
Full model with all fields comes later.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Paper(Base):
    """Academic paper metadata.

    Attributes:
        id: Unique identifier (paper_xxx format).
        title: Paper title.
        abstract: Paper abstract.
        authors: Comma-separated author names (simplified for skeleton).
        doi: Digital Object Identifier.
        venue: Publication venue (journal/conference name).
        year: Publication year.
        url: External URL to the paper.
        pdf_url: URL to the PDF file.
        created_at: When the record was created.
        updated_at: When the record was last updated.
    """

    __tablename__ = "papers"

    title: Mapped[str] = mapped_column(String(512), index=True)
    abstract: Mapped[str | None] = mapped_column(Text, default=None)
    authors: Mapped[str | None] = mapped_column(String(512), default=None)
    doi: Mapped[str | None] = mapped_column(String(256), unique=True, default=None)
    venue: Mapped[str | None] = mapped_column(String(256), default=None)
    year: Mapped[int | None] = mapped_column(default=None)
    url: Mapped[str | None] = mapped_column(String(1024), default=None)
    pdf_url: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Paper(id={self.id!r}, title={self.title[:50]!r})>"
