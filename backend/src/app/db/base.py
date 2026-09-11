"""SQLAlchemy base model and naming conventions.

Using SQLAlchemy 2.0 style with DeclarativeBase.
Naming convention ensures consistent index/constraint names across databases.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention for indexes, constraints, etc.
# See: https://docs.sqlalchemy.org/en/20/core/constraints.html#configuring-constraint-naming-conventions
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = metadata

    # Common columns available on all models
    id: Mapped[str] = mapped_column(primary_key=True, index=True)

    def to_dict(self) -> dict:
        """Convert model instance to a dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
