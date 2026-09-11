"""Stage 6: Survey Generation.

Generates the final answer/survey based on extracted evidence and reranked papers.
Uses LLM to produce a grounded, cited response.

For the skeleton, this is a stub that generates a template response.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class SurveyGenerationStage(BaseStage):
    """Generate the final survey/answer with citations."""

    def __init__(self) -> None:
        super().__init__(name="survey_generation")

    async def _execute(self, ctx: PipelineContext) -> None:
        reranked = ctx.get_state("reranked_papers", {})
        top_papers = reranked.get("top_k", [])
        evidence = ctx.get_state("evidence", {}).get("evidence", [])
        parsed = ctx.get_state("parsed_query", {})
        intent = parsed.get("intent", "find_paper")
        query = parsed.get("raw_query", ctx.query)

        logger.info(f"Generating survey for intent={intent}")

        # Stub: generate a template response
        answer = _generate_template_answer(query, top_papers, evidence, intent)

        result = {
            "answer": answer,
            "intent": intent,
            "citations_used": len(evidence),
            "papers_referenced": len(top_papers),
        }

        ctx.set_state("generated_answer", result)
        logger.info(f"Survey generated ({len(answer)} chars)")


def _generate_template_answer(
    query: str,
    papers: list[dict],
    evidence: list[dict],
    intent: str,
) -> str:
    """Generate a template answer for the skeleton.

    In production, this would be an LLM-generated response.
    """
    if intent == "survey":
        intro = f"Based on my analysis of {len(papers)} relevant papers, here is a comprehensive overview of '{query}':\n\n"
    elif intent == "compare":
        intro = f"Based on {len(papers)} papers, here is a comparison related to '{query}':\n\n"
    else:
        intro = f"Here are the most relevant papers for your query '{query}':\n\n"

    # List top papers
    body_parts = []
    for i, paper in enumerate(papers[:5], 1):
        authors = paper.get("authors", "Unknown")
        venue = paper.get("venue", "")
        year = paper.get("year", "")
        venue_year = f" ({venue}, {year})" if venue and year else ""
        body_parts.append(
            f"{i}. **{paper['title']}**\n"
            f"   - Authors: {authors}{venue_year}\n"
            f"   - Score: {paper.get('rerank_score', paper.get('score', 'N/A'))}\n"
            f"   - {paper.get('abstract', 'No abstract available.')[:150]}...\n"
        )

    body = "\n".join(body_parts)

    conclusion = (
        f"\n\n📊 **Summary**: Found {len(papers)} relevant papers. "
        f"Extracted {len(evidence)} evidence snippets supporting the query. "
        f"The top-ranked paper is '{papers[0]['title']}'." if papers else ""
    )

    disclaimer = (
        "\n\n---\n"
        "*This is a skeleton/demo response generated from mock data. "
        "In production, this would be an LLM-generated answer grounded in real paper content.*"
    )

    return intro + body + conclusion + disclaimer
