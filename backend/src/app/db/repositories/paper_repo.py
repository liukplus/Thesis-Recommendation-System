"""Paper repository with paper-specific queries."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.paper import Paper
from app.db.repositories.base import BaseRepository


class PaperRepository(BaseRepository[Paper]):
    """Repository for Paper model with paper-specific queries."""

    def __init__(self) -> None:
        super().__init__(model=Paper, id_prefix="paper")

    def search_by_title(
        self,
        session: Session,
        query: str,
        *,
        limit: int = 20,
    ) -> Sequence[Paper]:
        """Search papers by title (case-insensitive substring match).

        Args:
            session: Database session.
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            Matching papers ordered by title.
        """
        stmt = (
            select(Paper)
            .where(Paper.title.ilike(f"%{query}%"))
            .order_by(Paper.title)
            .limit(limit)
        )
        result = session.execute(stmt)
        return result.scalars().all()

    def get_by_doi(self, session: Session, doi: str) -> Optional[Paper]:
        """Get a paper by its DOI.

        Args:
            session: Database session.
            doi: The DOI to look up.

        Returns:
            The paper if found, None otherwise.
        """
        stmt = select(Paper).where(Paper.doi == doi)
        result = session.execute(stmt)
        return result.scalar_one_or_none()

    def search(
        self,
        session: Session,
        query: str,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[Paper]:
        """Full-text search across title and abstract.

        Args:
            session: Database session.
            query: Search query.
            skip: Number of results to skip.
            limit: Maximum number of results.

        Returns:
            Matching papers.
        """
        like_pattern = f"%{query}%"
        stmt = (
            select(Paper)
            .where(
                or_(
                    Paper.title.ilike(like_pattern),
                    Paper.abstract.ilike(like_pattern),
                )
            )
            .order_by(Paper.year.desc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        result = session.execute(stmt)
        return result.scalars().all()
