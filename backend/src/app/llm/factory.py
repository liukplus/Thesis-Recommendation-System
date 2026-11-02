"""LLM client factory.

Creates and caches the LLM client based on settings.
"""
from __future__ import annotations

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.llm.base import LLMClient
from app.llm.openai_compat import OpenAICompatClient

logger = get_logger(__name__)

_instance: LLMClient | None = None


def get_llm(settings: Settings | None = None) -> LLMClient:
    """Get the global LLM client instance.

    Creates one on first call using settings.

    Args:
        settings: Settings to use (uses global if None).

    Returns:
        The LLM client instance.
    """
    global _instance
    if _instance is None:
        if settings is None:
            settings = get_settings()
        _instance = OpenAICompatClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )
        logger.info(f"LLM client initialized (model={settings.llm_model})")
    return _instance


async def close_llm() -> None:
    """Close the global LLM client and release resources."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
        logger.info("LLM client closed")


def reset_llm() -> None:
    """Reset the global LLM client (for testing)."""
    global _instance
    _instance = None
