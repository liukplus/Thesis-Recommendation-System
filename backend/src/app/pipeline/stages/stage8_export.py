"""Stage 8: Export.

Exports the final result in various formats (markdown, JSON, BibTeX, etc.).

For the skeleton, this is a stub that produces markdown and JSON.
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class ExportStage(BaseStage):
    """Export pipeline results in multiple formats."""

    def __init__(self) -> None:
        super().__init__(name="export")

    async def _execute(self, ctx: PipelineContext) -> None:
        answer_data = ctx.get_state("generated_answer", {})
        answer = answer_data.get("answer", "")
        reranked = ctx.get_state("reranked_papers", {})
        papers = reranked.get("papers", [])

        logger.info("Exporting results")

        # Generate export formats
        markdown = _export_markdown(ctx, answer, papers)
        bibtex = _export_bibtex(papers)
        json_export = _export_json(ctx, answer, papers)

        result = {
            "formats": {
                "markdown": markdown,
                "bibtex": bibtex,
                "json": json_export,
            },
            "paper_count": len(papers),
        }

        ctx.set_state("export", result)
        logger.info(f"Export complete: {len(papers)} papers, 3 formats")


def _export_markdown(ctx: PipelineContext, answer: str, papers: list[dict]) -> str:
    """Export results as markdown."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    md = f"""# Research Report

**Query:** {ctx.query}

**Generated:** {timestamp}

**Trace ID:** {ctx.trace_id}

---

## Answer

{answer}

---

## References

"""
    for i, p in enumerate(papers, 1):
        authors = p.get("authors", "Unknown")
        venue = p.get("venue", "")
        year = p.get("year", "")
        doi = p.get("doi", "")
        md += f"[{i}] {authors}. *{p['title']}*. {venue}, {year}.\n"
        if doi:
            md += f"    DOI: {doi}\n"
        md += "\n"

    return md


def _export_bibtex(papers: list[dict]) -> str:
    """Export paper list as BibTeX entries."""
    entries = []
    for p in papers:
        key = p.get("id", "unknown").replace("paper_", "")
        authors = p.get("authors", "Unknown").replace(",", " and")
        title = p.get("title", "")
        venue = p.get("venue", "")
        year = p.get("year", "")
        doi = p.get("doi", "")

        entry = f"@article{{{key},\n"
        entry += f"  title = {{{title}}},\n"
        entry += f"  author = {{{authors}}},\n"
        entry += f"  journal = {{{venue}}},\n"
        entry += f"  year = {{{year}}},\n"
        if doi:
            entry += f"  doi = {{{doi}}},\n"
        entry += f"}}\n"
        entries.append(entry)

    return "\n".join(entries)


def _export_json(ctx: PipelineContext, answer: str, papers: list[dict]) -> str:
    """Export results as JSON string."""
    data = {
        "query": ctx.query,
        "trace_id": ctx.trace_id,
        "answer": answer,
        "success": ctx.success,
        "total_duration_ms": round(ctx.total_duration_ms, 2),
        "papers": [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "authors": p.get("authors", "").split(", ") if p.get("authors") else [],
                "venue": p.get("venue"),
                "year": p.get("year"),
                "doi": p.get("doi"),
                "score": p.get("rerank_score", p.get("score")),
            }
            for p in papers
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
