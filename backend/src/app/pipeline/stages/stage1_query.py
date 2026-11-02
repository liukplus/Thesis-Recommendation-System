"""Stage 1: Query Parsing.

Parses the raw user query into a typed ``QueryContract`` for downstream stages.
Extracts: keywords, research areas, year range, intent, etc.

For the skeleton, this is a stub that does basic keyword extraction + intent
classification; the extracted keywords stand in for ``methods`` until a real
topic/method split exists.
"""
from __future__ import annotations

import re

from app.core.logging import get_logger
from app.domain.contract import Intent, QueryContract
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext

logger = get_logger(__name__)


class QueryParseStage(BaseStage):
    """Parse user query into structured retrieval parameters."""

    def __init__(self) -> None:
        super().__init__(name="query_parse")

    async def _execute(self, ctx: PipelineContext) -> None:
        query = ctx.query.strip()
        logger.info(f"Parsing query: {query[:100]}")

        keywords = _extract_keywords(query)
        intent = Intent(_classify_intent(query))

        ctx.state.contract = QueryContract(
            topic=query,
            methods=keywords[:5],  # stub: top keywords as coarse method cues
            intent=intent,
        )
        logger.info(f"Query parsed: {len(keywords)} keywords, intent={intent.value}")


def _extract_keywords(query: str) -> list[str]:
    """Simple keyword extraction (stub implementation).

    Tokenizes, removes stopwords, returns ranked keywords.
    """
    # Tokenize (simple split on non-alphanumeric)
    tokens = re.findall(r"[a-zA-Z一-鿿][a-zA-Z一-鿿\-0-9]+", query.lower())

    # Common stopwords to filter out
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "dare",
        "ought", "used", "what", "which", "who", "whom", "this", "that",
        "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "me", "him", "her", "us", "them", "my", "your", "his", "its",
        "our", "their", "about", "into", "through", "during", "before",
        "after", "above", "below", "between", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there",
        "when", "where", "why", "how", "all", "each", "every", "both",
        "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "because", "as", "until", "while", "up", "down",
        "paper", "papers", "research", "study", "studies",
    }

    keywords = [t for t in tokens if t not in stopwords and len(t) > 2]

    # Deduplicate preserving order
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    return unique


def _classify_intent(query: str) -> str:
    """Simple intent classification (stub).

    Returns one of: survey, compare, find_method, find_paper, explain
    """
    q = query.lower()

    if any(w in q for w in ["survey", "综述", "overview", "review", "最新进展"]):
        return "survey"
    if any(w in q for w in ["compare", "对比", "比较", "vs", "versus"]):
        return "compare"
    if any(w in q for w in ["method", "方法", "how", "怎么", "如何实现"]):
        return "find_method"
    if any(w in q for w in ["explain", "解释", "what is", "是什么"]):
        return "explain"
    return "find_paper"
