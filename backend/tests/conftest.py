"""Shared pytest fixtures and test doubles for the backend test suite."""
from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChatModel(BaseChatModel):
    """Deterministic BaseChatModel double returning scripted AIMessages.

    Each call to ``_agenerate`` consumes the next response; the last response is
    reused if more calls are made than responses supplied.
    """

    def __init__(self, responses: list[AIMessage] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Underscore-prefixed so Pydantic's __setattr__ permits these undeclared
        # instance attributes (BaseChatModel is a Pydantic model in langchain-core 1.x).
        self._responses: list[AIMessage] = list(responses or [AIMessage(content="")])
        self._calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Sync generation is unsupported (async-only double)."""
        raise NotImplementedError("FakeChatModel is async-only")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        idx = min(self._calls, len(self._responses) - 1)
        self._calls += 1
        # Return a fresh copy with a cleared id, mirroring a real model (which emits a
        # new message each call). Reusing the same object would let ``add_messages``
        # mutate + dedupe it by its assigned id.
        message = self._responses[idx].model_copy(deep=True)
        message.id = None
        return ChatResult(generations=[ChatGeneration(message=message)])


class RaisingChatModel(BaseChatModel):
    """Model double whose generation always raises (simulates an LLM/network error)."""

    error: str = "LLM boom"

    @property
    def _llm_type(self) -> str:
        return "raising"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError(self.error)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError(self.error)


@pytest.fixture
def fake_chat_model():
    """Factory fixture: ``model = fake_chat_model([AIMessage(...)])``."""

    def _make(responses: list[AIMessage] | None = None) -> FakeChatModel:
        return FakeChatModel(responses)

    return _make


@pytest.fixture
def raising_chat_model():
    """Factory fixture: a chat model that raises on every call."""

    def _make(error: str = "LLM boom") -> RaisingChatModel:
        return RaisingChatModel(error=error)

    return _make
