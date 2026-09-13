"""Stage 2: Multi-source Recall.

Retrieves candidate papers from multiple sources (local DB, semantic/vector
search, external APIs). In the offline demo build this pulls from the shared
mock catalog (:mod:`app.mock`) with a deterministic source assignment, so the
same records appear across the REST ``/papers`` endpoints, the pipeline, and
the agent — just as they would when all three read from real backends.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.mock import search_mock_papers
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)

# The three logical retrieval sources the fusion stage expects.
_SOURCES = ("local_db", "semantic", "external")

# Number of unique candidates to recall from the demo catalog.
_RECALL_LIMIT = 12


class RecallStage(BaseStage):
    """Retrieve candidate papers from multiple sources."""

    def __init__(self) -> None:
        super().__init__(name="recall")

    async def _execute(self, ctx: PipelineContext) -> None:
        parsed = ctx.get_state("parsed_query", {})
        query = parsed.get("raw_query", ctx.query)

        logger.info(f"Recalling papers for query: {query[:80]}")

        # Shared offline catalog. A real deployment swaps this for DB + vector
        # index + external API clients behind the same candidate contract.
        hits = search_mock_papers(query, limit=_RECALL_LIMIT)

        # Spread hits across the three sources by rank to exercise fusion.
        candidates: list[dict] = []
        for rank, paper in enumerate(hits):
            paper["source"] = _SOURCES[rank % len(_SOURCES)]
            candidates.append(paper)

        # Re-surface the two most relevant papers from a second source. This
        # creates deliberate cross-source duplicates so the fusion/dedup stage
        # has something to merge (RRF boosts them, then dedup collapses them).
        if hits:
            candidates.append(_from_other_source(hits[0], candidates[0]["source"]))
        if len(hits) > 1:
            candidates.append(_from_other_source(hits[1], candidates[1]["source"]))

        recalled = {
            "total": len(candidates),
            "sources": {
                "local_db": [c for c in candidates if c["source"] == "local_db"],
                "semantic": [c for c in candidates if c["source"] == "semantic"],
                "external": [c for c in candidates if c["source"] == "external"],
            },
            "candidates": candidates,
        }

        ctx.set_state("recalled_papers", recalled)
        logger.info(
            f"Recalled {len(candidates)} candidates "
            f"({len(hits)} unique) from {len(_SOURCES)} sources"
        )


def _from_other_source(paper: dict, current_source: str) -> dict:
    """Return a shallow copy of a candidate attributed to a different source."""
    duplicate = dict(paper)
    other_sources = [s for s in _SOURCES if s != current_source]
    duplicate["source"] = other_sources[0]
    return duplicate
