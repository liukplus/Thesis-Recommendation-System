"""Stage 4: Reranking.

Reranks fused candidates using a cross-encoder or LLM-based scorer.
Produces the final ranked list of papers.

For the skeleton, this is a stub that passes through with a slight reorder.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class RerankStage(BaseStage):
    """Rerank candidate papers using relevance scoring."""

    def __init__(self) -> None:
        super().__init__(name="rerank")

    async def _execute(self, ctx: PipelineContext) -> None:
        fused = ctx.get_state("fused_papers", {})
        papers = fused.get("papers", [])
        parsed = ctx.get_state("parsed_query", {})
        query = parsed.get("raw_query", ctx.query)

        logger.info(f"Reranking {len(papers)} papers")

        # Stub: simulate reranking by adding a rerank_score
        # In production, this would call a reranker model or LLM
        reranked = _rerank_simple(papers, query)

        result = {
            "total": len(reranked),
            "papers": reranked,
            "top_k": reranked[:10],  # keep top 10 for downstream
        }

        ctx.set_state("reranked_papers", result)
        logger.info(f"Reranking complete: {len(reranked)} papers")


def _rerank_simple(papers: list[dict], query: str) -> list[dict]:
    """Simple reranking stub.

    Blends retrieval relevance, cross-source agreement (RRF) and citation
    impact. Papers whose text matched the query (``match == "keyword"``) are
    ranked strictly above popularity-only fallbacks, so a highly cited but
    off-topic paper can never bury a relevant one. A real implementation
    would replace this with a cross-encoder score.

    Args:
        papers: List of papers with 'score', 'fused_score', 'match' and
            'citation_count'.
        query: The query (unused in stub, used in real impl).

    Returns:
        Papers sorted by rerank_score descending.
    """
    if not papers:
        return []

    # Normalize signals to [0, 1]. RRF fused scores live on a tiny scale
    # (~1/(k+rank)), so raw values cannot be blended directly.
    max_citations = max((p.get("citation_count", 0) for p in papers), default=1)
    max_fused = max((p.get("fused_score", p.get("score", 0.5)) for p in papers), default=1.0)
    max_fused = max_fused or 1.0
    max_citations = max_citations or 1

    for p in papers:
        fused = p.get("fused_score", p.get("score", 0.5))
        rrf_signal = fused / max_fused
        citation_signal = p.get("citation_count", 0) / max_citations
        # Retrieval score from the offline keyword/fallback search.
        relevance = p.get("score", 0.5)

        if p.get("match", "keyword") == "keyword":
            # Band [0.60, 1.0]: relevance dominates, popularity only breaks ties.
            rerank_score = 0.60 + 0.25 * relevance + 0.08 * rrf_signal + 0.07 * citation_signal
        else:
            # Band [0.30, ~0.46]: query-matched papers always outrank these.
            rerank_score = 0.30 + 0.12 * relevance + 0.04 * rrf_signal + 0.04 * citation_signal
        p["rerank_score"] = round(min(rerank_score, 1.0), 4)

    # Sort by rerank score
    papers.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

    # Add rank
    for i, p in enumerate(papers):
        p["rank"] = i + 1

    return papers
