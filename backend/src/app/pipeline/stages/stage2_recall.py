"""Stage 2: Multi-source Recall.

Retrieves candidate papers from multiple sources (DB, vector search, external APIs).
For the skeleton, this is a stub that returns mock data as typed ``Paper`` records
and records the pass in a ``SearchRecord``.
"""
from __future__ import annotations

from typing import Any

from app.core.ids import new_id
from app.core.logging import get_logger
from app.domain.paper import Paper
from app.domain.record import SearchRecord
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class RecallStage(BaseStage):
    """Retrieve candidate papers from multiple sources."""

    def __init__(self) -> None:
        super().__init__(name="recall")

    async def _execute(self, ctx: PipelineContext) -> None:
        contract = ctx.state.contract
        keywords = contract.methods if contract else []
        topic = contract.topic if contract else ctx.query

        logger.info(f"Recalling papers for query: {topic[:80]}")

        papers = _generate_mock_candidates(keywords, topic)

        ctx.state.recalled = papers
        ctx.state.search_record = SearchRecord(
            record_id=new_id("recall"),
            query_text=topic,
            result_paper_ids=[p.paper_id for p in papers],
        )
        logger.info(f"Recalled {len(papers)} candidates from mock sources")


def _generate_mock_candidates(keywords: list[str], query: str) -> list[Paper]:
    """Generate mock candidate papers for the skeleton.

    In production, this would query real data sources.
    """
    kw_str = " ".join(keywords[:3]) if keywords else "machine learning"

    # Heterogeneous mock rows (str/list/int/float values) -> typed Papers below.
    templates: list[dict[str, Any]] = [
        {
            "paper_id": "paper_mock_001",
            "title": f"A Survey of {kw_str.title()} Techniques and Applications",
            "abstract": f"This paper presents a comprehensive survey of recent advances in {kw_str}. "
                        f"We review 150+ papers, categorize approaches, and identify future directions.",
            "authors": ["Alice Wang", "Bob Chen", "Carol Li"],
            "year": 2024,
            "venue": "ACM Computing Surveys",
            "citation_count": 156,
            "source": "local_db",
            "score": 0.92,
        },
        {
            "paper_id": "paper_mock_002",
            "title": f"Novel Approach to {kw_str.title()} Using Deep Neural Networks",
            "abstract": f"We propose a novel deep learning method for {kw_str} that achieves "
                        f"state-of-the-art performance on standard benchmarks.",
            "authors": ["David Zhang", "Eva Liu"],
            "year": 2024,
            "venue": "NeurIPS",
            "citation_count": 89,
            "source": "semantic",
            "score": 0.87,
        },
        {
            "paper_id": "paper_mock_003",
            "title": f"Efficient {kw_str.title()} with Limited Data",
            "abstract": f"We address the challenge of {kw_str} in low-resource settings, "
                        f"proposing a data-efficient framework that outperforms baselines by 15%.",
            "authors": ["Frank Zhao", "Grace Sun", "Henry Wu"],
            "year": 2023,
            "venue": "ICML",
            "citation_count": 234,
            "source": "external",
            "score": 0.81,
        },
        {
            "paper_id": "paper_mock_004",
            "title": f"Towards Generalizable {kw_str.title()} Models",
            "abstract": f"This work studies generalization in {kw_str} models across domains. "
                        f"We introduce a new benchmark and propose domain adaptation techniques.",
            "authors": ["Ivy Huang", "Jack Ma"],
            "year": 2024,
            "venue": "ICLR",
            "citation_count": 45,
            "source": "semantic",
            "score": 0.78,
        },
        {
            "paper_id": "paper_mock_005",
            "title": f"A Practical Guide to {kw_str.title()} for Industrial Applications",
            "abstract": f"We present practical considerations for deploying {kw_str} in production, "
                        f"including latency optimization and cost analysis.",
            "authors": ["Karen Xu", "Leo Qian", "Mia Yang"],
            "year": 2023,
            "venue": "KDD",
            "citation_count": 112,
            "source": "local_db",
            "score": 0.75,
        },
    ]

    return [Paper(**t) for t in templates]
