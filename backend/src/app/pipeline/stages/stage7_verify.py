"""Stage 7: Citation Verification.

Verifies that citations in the generated answer actually match the source paper content.
Two-level verification: (1) string match, (2) LLM-based semantic verification.

For the skeleton, this is a stub that passes everything through.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class CitationVerificationStage(BaseStage):
    """Verify citations in the generated answer."""

    def __init__(self) -> None:
        super().__init__(name="citation_verification")

    async def _execute(self, ctx: PipelineContext) -> None:
        answer_data = ctx.get_state("generated_answer", {})
        answer = answer_data.get("answer", "")
        evidence = ctx.get_state("evidence", {}).get("evidence", [])

        logger.info("Verifying citations (stub)")

        # Stub: simple verification — count citations vs evidence
        citations_found = answer.count("[")  # rough count
        verified_count = min(len(evidence), citations_found)

        result = {
            "verified": True,  # stub always passes
            "total_citations": citations_found,
            "verified_citations": verified_count,
            "failed_citations": [],
            "verification_level": "level1_string_match",
        }

        ctx.set_state("verified_answer", result)
        logger.info(
            f"Citation verification: {verified_count}/{citations_found} verified (stub)"
        )
