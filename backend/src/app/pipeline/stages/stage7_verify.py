"""Stage 7: Citation Verification.

Verifies that citations in the generated answer actually match source evidence.
Two-level verification (D8):
- L1 (string/existence) — the cited source exists among the extracted evidence.
- L2 (semantic support) — the evidence actually supports the cited claim.

For the skeleton, L1 is wired and L2 is a documented pass-through placeholder.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.survey import Survey
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class CitationVerificationStage(BaseStage):
    """Verify citations in the generated answer."""

    def __init__(self) -> None:
        super().__init__(name="citation_verification")

    async def _execute(self, ctx: PipelineContext) -> None:
        survey = ctx.state.survey
        if survey is None:
            ctx.state.verified = survey
            return

        evidence_paper_ids = {chunk.paper_id for chunk in ctx.state.evidence}

        # L1: a citation is retained only if its source exists in the evidence.
        verified_citations = [
            c for c in survey.citations if c.paper_id in evidence_paper_ids
        ]

        # L2 (semantic support): not implemented in this pass — pass-through.
        for citation in verified_citations:
            logger.debug(f"L1 verified citation [{citation.index}] -> {citation.paper_id}")

        ctx.state.verified = Survey(
            answer=survey.answer,
            citations=verified_citations,
        )
        logger.info(
            f"Citation verification: {len(verified_citations)}/{len(survey.citations)} "
            f"verified (L1); L2 deferred"
        )
