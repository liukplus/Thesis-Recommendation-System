"""Stage 2: Multi-source Recall.

Retrieves candidate papers from multiple sources (DB, vector search, external APIs).
For the skeleton, this is a stub that returns mock data.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class RecallStage(BaseStage):
    """Retrieve candidate papers from multiple sources."""

    def __init__(self) -> None:
        super().__init__(name="recall")

    async def _execute(self, ctx: PipelineContext) -> None:
        parsed = ctx.get_state("parsed_query", {})
        keywords = parsed.get("query_terms", [])
        query = parsed.get("raw_query", ctx.query)

        logger.info(f"Recalling papers for query: {query[:80]}")

        # Stub: return mock candidate papers
        candidates = _generate_mock_candidates(keywords, query)

        # Group by source
        recalled = {
            "total": len(candidates),
            "sources": {
                "local_db": [c for c in candidates if c["source"] == "local_db"],
                "semantic": [c for c in candidates if c["source"] == "semantic"],
                "external": [c for c in candidates if c["source"] == "external"],
            },
            "candidates": candidates,
        }

        ctx.set_state("recalled_papers", recalled)
        logger.info(f"Recalled {len(candidates)} candidates from 3 sources")


def _generate_mock_candidates(keywords: list[str], query: str) -> list[dict]:
    """Generate mock candidate papers for the skeleton.

    In production, this would query real data sources.
    """
    kw_str = " ".join(keywords[:3]) if keywords else "machine learning"

    templates = [
        {
            "id": "paper_mock_001",
            "title": f"A Survey of {kw_str.title()} Techniques and Applications",
            "abstract": f"This paper presents a comprehensive survey of recent advances in {kw_str}. "
                        f"We review 150+ papers, categorize approaches, and identify future directions.",
            "authors": "Alice Wang, Bob Chen, Carol Li",
            "year": 2024,
            "venue": "ACM Computing Surveys",
            "citation_count": 156,
            "source": "local_db",
            "score": 0.92,
        },
        {
            "id": "paper_mock_002",
            "title": f"Novel Approach to {kw_str.title()} Using Deep Neural Networks",
            "abstract": f"We propose a novel deep learning method for {kw_str} that achieves "
                        f"state-of-the-art performance on standard benchmarks.",
            "authors": "David Zhang, Eva Liu",
            "year": 2024,
            "venue": "NeurIPS",
            "citation_count": 89,
            "source": "semantic",
            "score": 0.87,
        },
        {
            "id": "paper_mock_003",
            "title": f"Efficient {kw_str.title()} with Limited Data",
            "abstract": f"We address the challenge of {kw_str} in low-resource settings, "
                        f"proposing a data-efficient framework that outperforms baselines by 15%.",
            "authors": "Frank Zhao, Grace Sun, Henry Wu",
            "year": 2023,
            "venue": "ICML",
            "citation_count": 234,
            "source": "external",
            "score": 0.81,
        },
        {
            "id": "paper_mock_004",
            "title": f"Towards Generalizable {kw_str.title()} Models",
            "abstract": f"This work studies generalization in {kw_str} models across domains. "
                        f"We introduce a new benchmark and propose domain adaptation techniques.",
            "authors": "Ivy Huang, Jack Ma",
            "year": 2024,
            "venue": "ICLR",
            "citation_count": 45,
            "source": "semantic",
            "score": 0.78,
        },
        {
            "id": "paper_mock_005",
            "title": f"A Practical Guide to {kw_str.title()} for Industrial Applications",
            "abstract": f"We present practical considerations for deploying {kw_str} in production, "
                        f"including latency optimization and cost analysis.",
            "authors": "Karen Xu, Leo Qian, Mia Yang",
            "year": 2023,
            "venue": "KDD",
            "citation_count": 112,
            "source": "local_db",
            "score": 0.75,
        },
    ]

    return templates
