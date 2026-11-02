"""Stage 5: Evidence Extraction.

Extracts key evidence sentences/paragraphs from top papers that support
the query. Used for grounded generation in the next stage.

For the skeleton, this is a stub that fabricates illustrative spans around a
verbatim ``abstract[:120]`` slice. Because the stored ``content`` is synthesized
(a "Key finding" wrapper, not a contiguous source substring), chunks are marked
``verbatim=False`` per D9; the verbatim slice itself is kept in ``anchor`` until
real extractive matching lands.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class EvidenceExtractionStage(BaseStage):
    """Extract evidence sentences from top papers."""

    def __init__(self) -> None:
        super().__init__(name="evidence_extraction")

    async def _execute(self, ctx: PipelineContext) -> None:
        top_papers = ctx.state.ranked[:5]
        logger.info(f"Extracting evidence from {len(top_papers)} top papers")

        evidence = _extract_mock_evidence(top_papers)

        ctx.state.evidence = evidence
        logger.info(f"Extracted {len(evidence)} evidence snippets")


def _extract_mock_evidence(papers: list[Paper]) -> list[EvidenceChunk]:
    """Generate mock evidence snippets for the skeleton.

    In production, this would do real sentence-level evidence extraction.
    """
    evidence: list[EvidenceChunk] = []
    for i, paper in enumerate(papers[:5]):
        for j in range(2 if i < 3 else 1):
            span = paper.abstract[:120]
            evidence.append(
                EvidenceChunk(
                    chunk_id=f"ev_{paper.paper_id}_{j}",
                    paper_id=paper.paper_id,
                    section="abstract",
                    content=f"Key finding {j + 1}: {span}...",
                    anchor=span,
                    verbatim=False,
                    reason=f"top-{i + 1} paper (rerank_score={paper.rerank_score})",
                )
            )
    return evidence
