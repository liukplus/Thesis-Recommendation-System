"""Base types and protocol for LLM clients.

All LLM implementations must satisfy the LLMClient Protocol.
This lets us swap providers without changing calling code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Protocol, runtime_checkable

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass
class ChatMessage:
    """A single chat message.

    Attributes:
        role: The role of the message sender.
        content: The text content of the message.
        tool_calls: Optional tool calls (for assistant messages).
        tool_call_id: Tool call ID (for tool responses).
        name: Tool name (for tool responses).
    """

    role: MessageRole
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to the OpenAI-compatible message dict format."""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class Usage:
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def sum(self) -> int:
        """Total tokens (alias for total_tokens)."""
        return self.total_tokens

    def add(self, other: "Usage") -> None:
        """Add another Usage's counts to this one."""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


@dataclass
class ChatResult:
    """Result of a chat completion call.

    Attributes:
        content: The generated text content.
        model: The model that generated the response.
        usage: Token usage statistics.
        tool_calls: Any tool calls in the response.
        finish_reason: Why the generation stopped (stop, tool_calls, length, etc.).
        raw: Raw response data (for debugging).
    """

    content: str = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMClient(Protocol):
    """Protocol that all LLM clients must implement.

    This lets us swap between providers (OpenAI, DeepSeek, Zhipu, etc.)
    without changing calling code.
    """

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

        Args:
            messages: List of chat messages.
            model: Model name override (uses client default if None).
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens to generate.
            tools: List of tool definitions (OpenAI format).
            response_format: Response format specification (e.g., {"type": "json_object"}).
            timeout: Request timeout in seconds.

        Returns:
            ChatResult with the response.
        """
        ...

    async def close(self) -> None:
        """Close the client and release resources."""
        ...
