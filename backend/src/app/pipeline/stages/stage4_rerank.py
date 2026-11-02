"""Stage 4: Reranking.

Reranks fused candidates using a cross-encoder or LLM-based scorer.
Produces the final ranked list of papers.

For the skeleton, this is a stub that combines fused and citation scores.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.paper import Paper
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class RerankStage(BaseStage):
    """Rerank candidate papers using relevance scoring."""

    def __init__(self) -> None:
        super().__init__(name="rerank")

    async def _execute(self, ctx: PipelineContext) -> None:
        papers = [p.model_copy(deep=True) for p in ctx.state.fused]
        logger.info(f"Reranking {len(papers)} papers")

        ranked = _rerank_simple(papers)

        ctx.state.ranked = ranked
        logger.info(f"Reranking complete: {len(ranked)} papers")


def _rerank_simple(papers: list[Paper]) -> list[Paper]:
    """Simple reranking stub.

    Uses a combination of fused_score and citation_count to produce a final
    relevance score. Real implementation would use a cross-encoder.

    Args:
        papers: Papers with ``fused_score`` and ``citation_count`` set.

    Returns:
        Papers sorted by ``rerank_score`` descending, with ``rank`` assigned.
    """
    if not papers:
        return []

    max_citations = max((p.citation_count for p in papers), default=1)

    for paper in papers:
        fused = paper.fused_score if paper.fused_score is not None else (paper.score or 0.5)
        citations = paper.citation_count
        normalized_cit = citations / max_citations if max_citations > 0 else 0

        # Weighted combination: 70% relevance, 30% citation impact
        paper.rerank_score = round(0.7 * fused + 0.3 * normalized_cit, 4)

    papers.sort(key=lambda p: p.rerank_score or 0, reverse=True)

    for i, paper in enumerate(papers):
        paper.rank = i + 1

    return papers
