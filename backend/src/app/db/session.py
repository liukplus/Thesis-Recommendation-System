"""Database session management.

Provides async-safe session creation and context managers.
Uses SQLite with WAL mode for development, configurable for Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.core import cat_integration
from app.core.logging import get_logger
from app.db.base import Base

logger = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _setup_sqlite_wal(engine: Engine) -> None:
    """Enable WAL mode on SQLite connections for better concurrent read performance."""

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ensure_sqlite_dir(db_url: str) -> None:
    """Ensure the directory for a SQLite database file exists."""
    if db_url.startswith("sqlite:///"):
        import os
        path = db_url.replace("sqlite:///", "")
        # Handle relative paths
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created database directory: {directory}")


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine (singleton).

    Returns:
        Configured SQLAlchemy Engine instance.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _ensure_sqlite_dir(settings.database_url)
        _engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False}
            if settings.database_url.startswith("sqlite")
            else {},
        )
        if settings.database_url.startswith("sqlite"):
            _setup_sqlite_wal(_engine)
        logger.info(f"Database engine initialized: {settings.database_url.split('://')[0]}://***")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory (singleton).

    Returns:
        Configured sessionmaker instance.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager that provides a database session.

    Usage:
        with get_session() as session:
            session.query(...).all()

    Yields:
        A new SQLAlchemy Session. Commits on success, rolls back on error.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
        cat_integration.metric("db.commit").count()
    except Exception:
        session.rollback()
        cat_integration.metric("db.rollback").count()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Initialize the database by creating all tables.

    Call this once at application startup.
    For production, use Alembic migrations instead.
    """
    # Import all models so they're registered with Base.metadata
    from app.db.models import paper  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def dispose_db() -> None:
    """Clean up database connections.

    Call this at application shutdown.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")
