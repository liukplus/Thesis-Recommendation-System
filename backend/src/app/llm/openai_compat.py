"""OpenAI-compatible LLM client using httpx.

Works with any provider that implements the OpenAI API:
- OpenAI
- DeepSeek
- Zhipu AI (GLM)
- Tongyi Qianwen
- vLLM / Ollama locally
- etc.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import Settings, get_settings
from app.core.exceptions import (
    LLMTimeoutError,
    LLMRateLimitError,
    LLMValidationError,
    ServiceUnavailableError,
)
from app.core.logging import get_logger
from app.llm.base import ChatMessage, ChatResult, Usage

logger = get_logger(__name__)


class OpenAICompatClient:
    """OpenAI-compatible LLM client using httpx.AsyncClient.

    Args:
        base_url: Base URL of the API endpoint (e.g., "https://api.deepseek.com/v1").
        api_key: API key for authentication.
        model: Default model to use.
        timeout: Default timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        response_format: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ChatResult:
        """Send a chat completion request.

        See LLMClient Protocol for full docs.
        """
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": [m.to_dict() for m in messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools is not None:
            payload["tools"] = tools
        if response_format is not None:
            payload["response_format"] = response_format

        try:
            resp = await self._client.post(
                "/chat/completions",
                json=payload,
                timeout=timeout or self.timeout,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"LLM request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise ServiceUnavailableError(f"LLM service unavailable: {e}") from e

        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise LLMRateLimitError(
                "LLM rate limit exceeded",
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 500:
            raise ServiceUnavailableError(
                f"LLM service returned {resp.status_code}: {resp.text[:200]}"
            )
        if resp.status_code >= 400:
            raise LLMValidationError(
                f"LLM request failed ({resp.status_code}): {resp.text[:500]}"
            )

        data = resp.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> ChatResult:
        """Parse the API response into a ChatResult."""
        choices = data.get("choices", [])
        if not choices:
            raise LLMValidationError("LLM response has no choices")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls", []) or []

        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ChatResult(
            content=content,
            model=data.get("model", self.model),
            usage=usage,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            raw=data,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.debug("OpenAICompatClient closed")


def create_client_from_settings(settings: Optional[Settings] = None) -> OpenAICompatClient:
    """Create an OpenAICompatClient from application settings.

    Args:
        settings: Settings instance (uses global if None).

    Returns:
        Configured OpenAICompatClient.
    """
    if settings is None:
        settings = get_settings()
    return OpenAICompatClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
    )
