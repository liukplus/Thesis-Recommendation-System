"""Stage 3: Fusion and Deduplication.

Fuses results from multiple recall sources using RRF (Reciprocal Rank Fusion),
removes duplicates by DOI/title similarity, and expands with citation context.

For the skeleton, this is a stub that does basic dedup and re-ranking over typed
``Paper`` records.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.paper import Paper
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class FusionStage(BaseStage):
    """Fuse and deduplicate multi-source recall results."""

    def __init__(self) -> None:
        super().__init__(name="fusion")

    async def _execute(self, ctx: PipelineContext) -> None:
        papers = ctx.state.recalled
        logger.info(f"Fusing {len(papers)} candidates")

        fused = _fuse_rrf(papers)
        deduped = _deduplicate(fused)

        ctx.state.fused = deduped
        logger.info(
            f"Fusion complete: {len(papers)} → {len(deduped)} papers "
            f"({len(papers) - len(deduped)} dupes removed)"
        )


def _fuse_rrf(candidates: list[Paper], k: int = 60) -> list[Paper]:
    """Reciprocal Rank Fusion (RRF) — stub implementation.

    Papers are grouped by source and ranked by recall score within each source;
    each paper's RRF score is the sum of ``1 / (k + rank)`` across sources.

    Args:
        candidates: Candidate papers with ``source`` and ``score`` set.
        k: RRF constant (typically 60).

    Returns:
        Papers with ``fused_score`` set, sorted by fused score descending.
    """
    sources: dict[str, list[Paper]] = {}
    for paper in candidates:
        sources.setdefault(paper.source or "unknown", []).append(paper)

    # Sort each source by recall score (descending).
    for src_papers in sources.values():
        src_papers.sort(key=lambda p: p.score or 0, reverse=True)

    rrf_scores: dict[str, float] = {}
    paper_map: dict[str, Paper] = {}
    for src_papers in sources.values():
        for rank, paper in enumerate(src_papers):
            paper_map[paper.paper_id] = paper
            rrf_scores[paper.paper_id] = rrf_scores.get(paper.paper_id, 0.0) + 1.0 / (k + rank + 1)

    sorted_ids = sorted(rrf_scores.keys(), key=lambda pid: rrf_scores[pid], reverse=True)

    result: list[Paper] = []
    for pid in sorted_ids:
        paper = paper_map[pid].model_copy(deep=True)
        paper.fused_score = round(rrf_scores[pid], 6)
        result.append(paper)

    return result


def _deduplicate(papers: list[Paper]) -> list[Paper]:
    """Remove duplicate papers (stub: dedup by id only).

    Real implementation would use title similarity and DOI matching.
    """
    seen_ids: set[str] = set()
    result: list[Paper] = []
    for paper in papers:
        if paper.paper_id and paper.paper_id not in seen_ids:
            seen_ids.add(paper.paper_id)
            result.append(paper)
    return result
