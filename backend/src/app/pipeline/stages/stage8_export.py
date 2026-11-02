"""Stage 8: Export.

Exports the final result in various formats (markdown, JSON, BibTeX, etc.).

For the skeleton, this is a stub that produces markdown, BibTeX and JSON from the
verified survey and the ranked paper list.
"""
from __future__ import annotations

import json
from datetime import datetime

from app.core.logging import get_logger
from app.domain.export import Export
from app.domain.paper import Paper
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class ExportStage(BaseStage):
    """Export pipeline results in multiple formats."""

    def __init__(self) -> None:
        super().__init__(name="export")

    async def _execute(self, ctx: PipelineContext) -> None:
        verified = ctx.state.verified
        answer = verified.answer if verified else ""
        papers = ctx.state.ranked

        logger.info("Exporting results")

        markdown = _export_markdown(ctx, answer, papers)
        bibtex = _export_bibtex(papers)
        json_export = _export_json(ctx, answer, papers)

        ctx.state.exports = Export(
            formats={
                "markdown": markdown,
                "bibtex": bibtex,
                "json": json_export,
            },
        )
        logger.info(f"Export complete: {len(papers)} papers, 3 formats")


def _export_markdown(ctx: PipelineContext, answer: str, papers: list[Paper]) -> str:
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
    for i, paper in enumerate(papers, 1):
        authors = ", ".join(paper.authors) or "Unknown"
        md += f"[{i}] {authors}. *{paper.title}*. {paper.venue or ''}, {paper.year or ''}.\n"
        if paper.doi:
            md += f"    DOI: {paper.doi}\n"
        md += "\n"

    return md


def _export_bibtex(papers: list[Paper]) -> str:
    """Export paper list as BibTeX entries."""
    entries = []
    for paper in papers:
        key = paper.paper_id.replace("paper_", "")
        authors = ", ".join(paper.authors).replace(",", " and") if paper.authors else "Unknown"

        entry = f"@article{{{key},\n"
        entry += f"  title = {{{paper.title}}},\n"
        entry += f"  author = {{{authors}}},\n"
        entry += f"  journal = {{{paper.venue or ''}}},\n"
        entry += f"  year = {{{paper.year or ''}}},\n"
        if paper.doi:
            entry += f"  doi = {{{paper.doi}}},\n"
        entry += "}\n"
        entries.append(entry)

    return "\n".join(entries)


def _export_json(ctx: PipelineContext, answer: str, papers: list[Paper]) -> str:
    """Export results as JSON string."""
    # Under the compiled graph a fresh context is rebuilt per node, so aggregate
    # timing is the sum of recorded per-stage durations (see graphs/pipeline.py).
    total_duration_ms = sum(r.duration_ms for r in ctx.stage_results)
    data = {
        "query": ctx.query,
        "trace_id": ctx.trace_id,
        "answer": answer,
        "success": ctx.success,
        "total_duration_ms": round(total_duration_ms, 2),
        "papers": [
            {
                "id": p.paper_id,
                "title": p.title,
                "authors": p.authors,
                "venue": p.venue,
                "year": p.year,
                "doi": p.doi,
                "score": p.rerank_score if p.rerank_score is not None else p.score,
            }
            for p in papers
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
