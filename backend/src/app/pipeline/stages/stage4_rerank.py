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

    Uses a combination of fused_score and citation_count to produce a
    final relevance score. Real implementation would use a cross-encoder.

    Args:
        papers: List of papers with 'fused_score' and 'citation_count'.
        query: The query (unused in stub, used in real impl).

    Returns:
        Papers sorted by rerank_score descending.
    """
    if not papers:
        return []

    # Normalize citation counts to [0, 1]
    max_citations = max((p.get("citation_count", 0) for p in papers), default=1)

    for p in papers:
        fused = p.get("fused_score", p.get("score", 0.5))
        citations = p.get("citation_count", 0)
        normalized_cit = citations / max_citations if max_citations > 0 else 0

        # Weighted combination: 70% relevance, 30% citation impact
        rerank_score = 0.7 * fused + 0.3 * normalized_cit
        p["rerank_score"] = round(rerank_score, 4)

    # Sort by rerank score
    papers.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

    # Add rank
    for i, p in enumerate(papers):
        p["rank"] = i + 1

    return papers
