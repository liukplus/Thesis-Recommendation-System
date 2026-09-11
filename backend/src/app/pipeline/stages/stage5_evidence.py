"""Stage 5: Evidence Extraction.

Extracts key evidence sentences/paragraphs from top papers that support
the query. Used for grounded generation in the next stage.

For the skeleton, this is a stub.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class EvidenceExtractionStage(BaseStage):
    """Extract evidence sentences from top papers."""

    def __init__(self) -> None:
        super().__init__(name="evidence_extraction")

    async def _execute(self, ctx: PipelineContext) -> None:
        reranked = ctx.get_state("reranked_papers", {})
        top_papers = reranked.get("top_k", [])

        logger.info(f"Extracting evidence from {len(top_papers)} top papers")

        # Stub: generate mock evidence snippets
        evidence = _extract_mock_evidence(top_papers)

        result = {
            "total_evidence": len(evidence),
            "evidence": evidence,
        }

        ctx.set_state("evidence", result)
        logger.info(f"Extracted {len(evidence)} evidence snippets")


def _extract_mock_evidence(papers: list[dict]) -> list[dict]:
    """Generate mock evidence snippets for the skeleton.

    In production, this would do real sentence-level evidence extraction.
    """
    evidence = []
    for i, paper in enumerate(papers[:5]):
        # Generate 1-2 evidence snippets per paper
        for j in range(2 if i < 3 else 1):
            evidence.append({
                "paper_id": paper["id"],
                "paper_title": paper["title"],
                "evidence_id": f"ev_{paper['id']}_{j}",
                "text": f"Key finding {j+1}: {paper['abstract'][:120]}...",
                "relevance_score": round(0.9 - j * 0.15 - i * 0.05, 3),
                "section": "abstract",
            })
    return evidence
