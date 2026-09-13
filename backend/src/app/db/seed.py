"""Seed the database with demo papers.

Populates the ``papers`` table with the bundled mock catalog so the REST
endpoints (and any code that reads from the local DB source) have data in a
fresh demo environment. Seeding is idempotent: if the table already has rows
it is left untouched unless ``reset=True``.

Usage:
    # create tables + seed (safe to re-run)
    python -m app.db.seed

    # wipe and reload the demo data
    python -m app.db.seed --reset
"""
from __future__ import annotations

import argparse

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models.paper import Paper
from app.db.session import get_session, init_db
from app.mock import demo_db_rows

logger = get_logger(__name__)


def seed_demo_papers(
    session: Session | None = None,
    *,
    reset: bool = False,
) -> int:
    """Seed the papers table with the demo catalog.

    Args:
        session: An existing SQLAlchemy session. If None, opens (and commits)
            its own session against the configured engine.
        reset: If True, delete existing paper rows before inserting.

    Returns:
        Number of demo papers inserted. 0 when skipped because the table is
        already populated and reset is False.
    """
    if session is None:
        with get_session() as own_session:
            return _seed(own_session, reset=reset)
    return _seed(session, reset=reset)


def _seed(session: Session, *, reset: bool) -> int:
    existing = session.scalar(select(func.count()).select_from(Paper)) or 0

    if existing > 0 and not reset:
        logger.info(f"Seed skipped: papers table already has {existing} rows")
        return 0

    if reset and existing > 0:
        session.execute(delete(Paper))
        session.flush()
        logger.info(f"Cleared {existing} existing paper rows before seeding")

    rows = demo_db_rows()
    for row in rows:
        session.add(Paper(**row))
    session.flush()

    logger.info(f"Seeded {len(rows)} demo papers")
    return len(rows)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo papers into the database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing papers before inserting the demo catalog.",
    )
    args = parser.parse_args()

    init_db()
    inserted = seed_demo_papers(reset=args.reset)
    if inserted:
        print(f"Seeded {inserted} demo papers.")
    else:
        print("Seed skipped: database already contains papers (use --reset to reload).")


if __name__ == "__main__":
    _main()
