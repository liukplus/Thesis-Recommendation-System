"""Repository layer (data access objects)."""

from app.db.repositories.base import BaseRepository
from app.db.repositories.paper_repo import PaperRepository

__all__ = ["BaseRepository", "PaperRepository"]
