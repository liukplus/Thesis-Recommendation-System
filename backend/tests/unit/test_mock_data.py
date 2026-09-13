"""Tests for the demo mock catalog, offline search, and DB seeding."""
from __future__ import annotations

import pytest
from app.db.base import Base
from app.db.models.paper import Paper  # noqa: F401  (register model on Base)
from app.db.seed import seed_demo_papers
from app.mock import PAPER_CATALOG, demo_db_rows, search_mock_papers
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


class TestCatalog:
    def test_catalog_is_non_empty_and_ids_unique(self):
        assert len(PAPER_CATALOG) >= 20
        ids = [p["id"] for p in PAPER_CATALOG]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize(
        "field",
        ["id", "title", "abstract", "authors", "year", "venue", "citation_count", "topics"],
    )
    def test_every_paper_has_core_fields(self, field):
        for paper in PAPER_CATALOG:
            assert paper.get(field) not in (None, "", [])

    def test_db_rows_match_table_columns(self):
        rows = demo_db_rows()
        assert len(rows) == len(PAPER_CATALOG)
        allowed = {
            "id", "title", "abstract", "authors", "doi", "venue", "year", "url", "pdf_url"
        }
        for row in rows:
            assert set(row) == allowed


class TestMockSearch:
    def test_respects_limit_and_orders_by_score(self):
        results = search_mock_papers("deep learning", limit=5)
        assert len(results) == 5
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        assert all(0.0 <= s <= 1.0 for s in scores)

    def test_transformer_query_finds_transformer_paper(self):
        top = search_mock_papers("transformer architecture", limit=1)[0]
        blob = (top["title"] + " " + top["abstract"]).lower()
        assert "attention" in blob or "transformer" in blob

    def test_rag_query_ranks_rag_paper_first(self):
        top = search_mock_papers("retrieval augmented generation", limit=1)[0]
        assert "retrieval" in top["title"].lower()

    def test_graph_query_surfaces_all_gnn_papers(self):
        results = search_mock_papers("graph neural networks", limit=5)
        top_three = {r["id"] for r in results[:3]}
        assert top_three == {"paper_demo_0019", "paper_demo_0020", "paper_demo_0021"}
        # Generic "neural network" papers must not outrank the topical hits.
        assert results[3]["match"] == "keyword"

    def test_rl_query_surfaces_policy_papers(self):
        results = search_mock_papers("reinforcement learning policy gradient", limit=3)
        titles = " ".join(r["title"].lower() for r in results)
        assert "proximal policy optimization" in titles
        assert "reinforcement learning" in titles

    def test_unmatched_query_falls_back_to_results(self):
        results = search_mock_papers("zzzz qqqq unrelated", limit=6)
        assert len(results) == 6
        assert all(r["match"] == "fallback" for r in results)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_returns_independent_copies(self):
        first = search_mock_papers("graph neural networks", limit=5)
        original_title = first[0]["title"]
        first[0]["title"] = "MUTATED"
        again = search_mock_papers("graph neural networks", limit=5)
        assert again[0]["title"] == original_title


class TestDemoSeeding:
    @pytest.fixture()
    def session(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        with Session(engine) as session:
            yield session

    def test_seed_then_skip_then_reset(self, session):
        inserted = seed_demo_papers(session)
        session.commit()
        assert inserted == len(PAPER_CATALOG)
        assert session.scalar(select(func.count()).select_from(Paper)) == len(PAPER_CATALOG)

        # Idempotent: a second run inserts nothing.
        assert seed_demo_papers(session) == 0

        # Reset wipes and reloads the same number of rows.
        reset = seed_demo_papers(session, reset=True)
        session.commit()
        assert reset == len(PAPER_CATALOG)
        assert session.scalar(select(func.count()).select_from(Paper)) == len(PAPER_CATALOG)
