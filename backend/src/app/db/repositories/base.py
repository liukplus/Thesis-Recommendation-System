"""Base repository with generic CRUD operations.

All repositories inherit from this to get standard CRUD methods.
Model-specific logic goes in the subclass.
"""
from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.core.ids import new_id

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base class for all repositories.

    Provides standard CRUD operations. Subclass and add model-specific methods.

    Type Args:
        ModelType: The SQLAlchemy model class this repository manages.
    """

    def __init__(self, model: Type[ModelType], id_prefix: str) -> None:
        """Initialize the repository.

        Args:
            model: The SQLAlchemy model class.
            id_prefix: Prefix for generated IDs (e.g., "paper").
        """
        self.model = model
        self.id_prefix = id_prefix

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(self, session: Session, item_id: str) -> Optional[ModelType]:
        """Get an item by its primary key ID.

        Args:
            session: Database session.
            item_id: The item's ID.

        Returns:
            The item if found, None otherwise.
        """
        return session.get(self.model, item_id)

    def list_all(
        self,
        session: Session,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelType]:
        """List all items with pagination.

        Args:
            session: Database session.
            skip: Number of items to skip.
            limit: Maximum number of items to return.

        Returns:
            Sequence of items.
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = session.execute(stmt)
        return result.scalars().all()

    def count(self, session: Session) -> int:
        """Count total number of items.

        Args:
            session: Database session.

        Returns:
            Total count.
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        result = session.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, session: Session, **kwargs: Any) -> ModelType:
        """Create a new item.

        If 'id' is not provided in kwargs, a new ID is generated.

        Args:
            session: Database session.
            **kwargs: Model field values.

        Returns:
            The created item.
        """
        if "id" not in kwargs:
            kwargs["id"] = new_id(self.id_prefix)
        instance = self.model(**kwargs)
        session.add(instance)
        session.flush()
        return instance

    def update(
        self,
        session: Session,
        item: ModelType,
        **kwargs: Any,
    ) -> ModelType:
        """Update an existing item.

        Args:
            session: Database session.
            item: The item to update.
            **kwargs: Fields to update.

        Returns:
            The updated item.
        """
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        session.flush()
        return item

    def delete(self, session: Session, item: ModelType) -> None:
        """Delete an item.

        Args:
            session: Database session.
            item: The item to delete.
        """
        session.delete(item)
        session.flush()

    def delete_by_id(self, session: Session, item_id: str) -> bool:
        """Delete an item by ID.

        Args:
            session: Database session.
            item_id: The item's ID.

        Returns:
            True if an item was deleted, False if not found.
        """
        item = self.get_by_id(session, item_id)
        if item is None:
            return False
        self.delete(session, item)
        return True
