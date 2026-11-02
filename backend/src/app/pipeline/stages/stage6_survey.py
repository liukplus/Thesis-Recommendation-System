"""Stage 6: Survey Generation.

Generates the final answer/survey based on extracted evidence and reranked papers.
Uses LLM to produce a grounded, cited response.

For the skeleton, this is a stub that generates a template response and attaches
pre-numbered citations (D7: only ``[1..N]``, never fabricated numbers).
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.contract import Intent
from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.domain.survey import Citation, Survey
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class SurveyGenerationStage(BaseStage):
    """Generate the final survey/answer with citations."""

    def __init__(self) -> None:
        super().__init__(name="survey_generation")

    async def _execute(self, ctx: PipelineContext) -> None:
        top_papers = ctx.state.ranked[:5]
        evidence = ctx.state.evidence
        contract = ctx.state.contract
        intent = contract.intent if contract else Intent.FIND_PAPER
        topic = contract.topic if contract else ctx.query

        logger.info(f"Generating survey for intent={intent.value}")

        answer = _generate_template_answer(topic, top_papers, evidence, intent)
        citations = _build_citations(top_papers, evidence)

        ctx.state.survey = Survey(answer=answer, citations=citations)
        logger.info(f"Survey generated ({len(answer)} chars, {len(citations)} citations)")


def _build_citations(papers: list[Paper], evidence: list[EvidenceChunk]) -> list[Citation]:
    """Link each cited paper to its first evidence chunk, numbered from 1."""
    first_chunk: dict[str, str] = {}
    for chunk in evidence:
        first_chunk.setdefault(chunk.paper_id, chunk.chunk_id)

    return [
        Citation(
            index=i,
            paper_id=papers[i - 1].paper_id,
            chunk_id=first_chunk.get(papers[i - 1].paper_id),
        )
        for i in range(1, len(papers) + 1)
    ]


def _generate_template_answer(
    query: str,
    papers: list[Paper],
    evidence: list[EvidenceChunk],
    intent: Intent,
) -> str:
    """Generate a template answer for the skeleton.

    In production, this would be an LLM-generated response.
    """
    if intent is Intent.SURVEY:
        intro = f"Based on my analysis of {len(papers)} relevant papers, here is a comprehensive overview of '{query}':\n\n"
    elif intent is Intent.COMPARE:
        intro = f"Based on {len(papers)} papers, here is a comparison related to '{query}':\n\n"
    else:
        intro = f"Here are the most relevant papers for your query '{query}':\n\n"

    body_parts = []
    for i, paper in enumerate(papers, 1):
        authors = ", ".join(paper.authors) or "Unknown"
        venue = paper.venue or ""
        year = paper.year or ""
        venue_year = f" ({venue}, {year})" if venue and year else ""
        score = paper.rerank_score if paper.rerank_score is not None else paper.score
        body_parts.append(
            f"{i}. **{paper.title}**\n"
            f"   - Authors: {authors}{venue_year}\n"
            f"   - Score: {score}\n"
            f"   - {paper.abstract[:150] or 'No abstract available.'}...\n"
        )

    body = "\n".join(body_parts)

    conclusion = (
        f"\n\n📊 **Summary**: Found {len(papers)} relevant papers. "
        f"Extracted {len(evidence)} evidence snippets supporting the query. "
        f"The top-ranked paper is '{papers[0].title}'." if papers else ""
    )

    disclaimer = (
        "\n\n---\n"
        "*This is a skeleton/demo response generated from mock data. "
        "In production, this would be an LLM-generated answer grounded in real paper content.*"
    )

    return intro + body + conclusion + disclaimer
