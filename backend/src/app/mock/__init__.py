"""Mock data for offline demos.

This package ships a small, self-contained catalog of well-known AI/ML
papers plus a dependency-free keyword search over it. It lets the whole
system (pipeline recall, the agent's ``search_stub`` tool, and the
``/papers`` REST endpoints) run a convincing demo without an LLM key,
embedding model, vector database, or external APIs.

Nothing here is used when real retrieval is wired in — the catalog is a
stand-in behind the same seams the production implementations will use.
"""
from __future__ import annotations

from app.mock.papers import (
    PAPER_CATALOG,
    demo_db_rows,
    search_mock_papers,
)

__all__ = ["PAPER_CATALOG", "demo_db_rows", "search_mock_papers"]
