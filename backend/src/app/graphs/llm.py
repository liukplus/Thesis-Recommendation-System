"""LangChain ``BaseChatModel`` adapters over the existing ``LLMClient``.

Two models are provided:

- ``LangChainChatModel`` wraps an ``OpenAICompatClient`` so ``bind(tools=[...])``,
  ``ainvoke`` and the ``add_messages`` reducer all behave like any LangChain model.
- ``RuleBasedChatModel`` ports the rule-based fallback from the old ReAct loop so the
  graph still works when no API key is configured (``get_llm_client() -> None``).
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    UsageMetadata,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from app.llm.base import ChatMessage, LLMClient, Usage
from app.llm.base import ChatResult as LLMChatResult

# Keywords used by the rule-based model to decide whether the goal is a research query.
RESEARCH_KEYWORDS = [
    "paper", "survey", "research", "study", "论文", "综述", "研究",
    "what", "how", "why", "explain", "什么", "怎么", "如何",
]


def _content_of(message: BaseMessage) -> str:
    """Extract plain-text content from any LangChain message."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content)


def _tool_call_to_openai(tc: dict[str, Any]) -> dict[str, Any]:
    """Convert a LangChain tool call dict to the OpenAI wire format."""
    return {
        "id": tc.get("id", ""),
        "type": "function",
        "function": {
            "name": tc.get("name", ""),
            "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
        },
    }


def _to_chat_message(message: BaseMessage) -> ChatMessage:
    """Convert a LangChain message to the app's ``ChatMessage``."""
    if isinstance(message, SystemMessage):
        return ChatMessage(role="system", content=_content_of(message))
    if isinstance(message, HumanMessage):
        return ChatMessage(role="user", content=_content_of(message))
    if isinstance(message, ToolMessage):
        return ChatMessage(
            role="tool",
            content=_content_of(message),
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
    tool_calls = [
        _tool_call_to_openai(tc) for tc in (getattr(message, "tool_calls", None) or [])
        if isinstance(tc, dict)
    ]
    return ChatMessage(role="assistant", content=_content_of(message), tool_calls=tool_calls)


def _parse_json_args(arguments: str) -> dict[str, Any]:
    """Parse a JSON-encoded tool arguments string into a dict."""
    if not arguments:
        return {}
    try:
        data = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {"value": data}


def _to_ai_message(result: LLMChatResult) -> AIMessage:
    """Convert the app's ``ChatResult`` into a LangChain ``AIMessage``."""
    tool_calls = [
        {
            "name": tc["function"]["name"],
            "args": _parse_json_args(tc["function"].get("arguments", "{}")),
            "id": tc.get("id", ""),
            "type": "tool_call",
        }
        for tc in result.tool_calls
    ]
    ai_msg = AIMessage(content=result.content, tool_calls=tool_calls)
    ai_msg.usage_metadata = UsageMetadata(
        input_tokens=result.usage.prompt_tokens,
        output_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
    )
    return ai_msg


class LangChainChatModel(BaseChatModel):
    """Wrap an ``LLMClient`` (OpenAI-compatible) as a LangChain ``BaseChatModel``."""

    def __init__(
        self,
        client: LLMClient,
        model: str,
        *,
        temperature: float | None = 0.2,
        max_tokens: int | None = 2000,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._client = client
        self._model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def _llm_type(self) -> str:
        return "openai-compat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Sync generation is unsupported; the client is async-only."""
        raise NotImplementedError("LangChainChatModel is async-only")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        tools = kwargs.get("tools")
        chat_messages = [_to_chat_message(m) for m in messages]
        result = await self._client.chat(
            chat_messages,
            model=self._model_name,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            tools=tools,
        )
        ai_msg = _to_ai_message(result)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])


class RuleBasedChatModel(BaseChatModel):
    """Rule-based fallback model used when no API key is configured.

    Mirrors the logic previously in ``AgentRuntime._rule_based_think`` so the compiled
    graph still exercises the full ReAct loop (tool call → result → answer) with no LLM.
    """

    @property
    def _llm_type(self) -> str:
        return "rule-based"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("RuleBasedChatModel is async-only")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        goal = ""
        for m in messages:
            if isinstance(m, HumanMessage):
                goal = _content_of(m)

        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        if tool_messages and isinstance(messages[-1], ToolMessage):
            return _summarize_tool_result(goal, messages[-1])

        if any(kw in goal.lower() for kw in RESEARCH_KEYWORDS):
            return _research_tool_call(goal)
        return _hello(goal)


def _hello(goal: str) -> ChatResult:
    content = (
        f"Hello! I'm your research assistant. You asked about: {goal}\n\n"
        f"I found some relevant information for you. Since this is a demo "
        f"running without an LLM backend, I'll provide a template response.\n\n"
        f"**Key points:**\n"
        f"- You can configure an LLM provider in settings to enable "
        f"full AI-powered research assistance\n"
        f"- The system supports multi-step reasoning with tools\n"
        f"- Try searching for specific research topics\n\n"
        f"Let me know if you'd like to explore a specific area further!"
    )
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def _research_tool_call(goal: str) -> ChatResult:
    ai_msg = AIMessage(
        content=(
            f"I need to research '{goal}'. "
            f"Let me run the research pipeline to find and synthesize relevant papers."
        ),
        tool_calls=[{
            "name": "run_research",
            "args": {"query": goal},
            "id": "call_rule_001",
            "type": "tool_call",
        }],
    )
    return ChatResult(generations=[ChatGeneration(message=ai_msg)])


def _summarize_tool_result(goal: str, tool_message: ToolMessage) -> ChatResult:
    """Turn a ``run_research`` result into the final answer.

    The pipeline already returns a synthesized, cited ``answer``; the rule-based
    model relays it directly rather than re-summarizing.
    """
    raw = _content_of(tool_message)
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        result = raw

    if isinstance(result, dict):
        answer = result.get("answer") or ""
        papers = result.get("papers") or []
        if answer:
            suffix = f"\n\n_({len(papers)} ranked papers returned.)_" if papers else ""
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=answer + suffix))]
            )

    return ChatResult(
        generations=[
            ChatGeneration(
                message=AIMessage(
                    content=f"Here's the result from {tool_message.name or 'the tool'}: "
                    f"{str(result)[:500]}"
                )
            )
        ]
    )


def get_chat_model(client: LLMClient | None = None) -> BaseChatModel:
    """Build a chat model, preferring the configured LLM client when available.

    Builds a fresh wrapper on every call (the underlying ``LLMClient`` is shared via the
    factory); this keeps per-request state (such as usage tracking) free of races.
    """
    if client is None:
        return RuleBasedChatModel()
    return LangChainChatModel(client=client, model=getattr(client, "model", ""))


# Re-exported for convenience (kept importable under the original name).
__all__ = [
    "LangChainChatModel",
    "RuleBasedChatModel",
    "Usage",
    "get_chat_model",
]
