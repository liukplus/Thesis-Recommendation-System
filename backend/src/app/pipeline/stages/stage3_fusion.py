"""Stage 3: Fusion and Deduplication.

Fuses results from multiple recall sources using RRF (Reciprocal Rank Fusion),
removes duplicates by DOI/title similarity, and expands with citation context.

For the skeleton, this is a stub that does basic dedup and re-ranking.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class FusionStage(BaseStage):
    """Fuse and deduplicate multi-source recall results."""

    def __init__(self) -> None:
        super().__init__(name="fusion")

    async def _execute(self, ctx: PipelineContext) -> None:
        recalled = ctx.get_state("recalled_papers", {})
        candidates = recalled.get("candidates", [])

        logger.info(f"Fusing {len(candidates)} candidates")

        # Stub: simple dedup by id and sort by score
        fused = _fuse_rrf(candidates)
        deduped = _deduplicate(fused)

        result = {
            "total_before": len(candidates),
            "total_after": len(deduped),
            "duplicates_removed": len(candidates) - len(deduped),
            "papers": deduped,
        }

        ctx.set_state("fused_papers", result)
        logger.info(
            f"Fusion complete: {len(candidates)} → {len(deduped)} papers "
            f"({len(candidates) - len(deduped)} dupes removed)"
        )


def _fuse_rrf(candidates: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion (RRF) — stub implementation.

    Since our mock data comes from different sources with scores,
    we use a simplified RRF based on per-source rankings.

    Args:
        candidates: List of candidate papers with 'source' and 'score'.
        k: RRF constant (typically 60).

    Returns:
        Papers with fused scores, sorted by fused score descending.
    """
    # Group by source
    sources: dict[str, list[dict]] = {}
    for c in candidates:
        src = c.get("source", "unknown")
        sources.setdefault(src, []).append(c)

    # Sort each source by score
    for src in sources:
        sources[src].sort(key=lambda x: x.get("score", 0), reverse=True)

    # Compute RRF scores
    rrf_scores: dict[str, float] = {}
    paper_map: dict[str, dict] = {}

    for src, papers in sources.items():
        for rank, paper in enumerate(papers):
            pid = paper["id"]
            paper_map[pid] = paper
            # RRF formula: 1 / (k + rank)
            rrf_scores[pid] = rrf_scores.get(pid, 0) + 1.0 / (k + rank + 1)

    # Sort by fused score
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    # Build result with fused score
    result = []
    for pid in sorted_ids:
        paper = dict(paper_map[pid])  # copy
        paper["fused_score"] = round(rrf_scores[pid], 6)
        result.append(paper)

    return result


def _deduplicate(papers: list[dict]) -> list[dict]:
    """Remove duplicate papers (stub: dedup by id only).

    Real implementation would use title similarity and DOI matching.
    """
    seen_ids = set()
    result = []
    for p in papers:
        pid = p.get("id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            result.append(p)
    return result
