"""Tool registry and base tool specification.

Tools are functions the agent can call. Each tool has:
- name: unique identifier
- description: used by the LLM to decide when to use the tool
- input_schema: Pydantic model describing the arguments
- handler: async function that executes the tool

The TOOL_REGISTRY is the central registry of all available tools.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.mock import search_mock_papers

logger = get_logger(__name__)


@dataclass
class ToolSpec:
    """Specification for a tool the agent can call.

    Attributes:
        name: Unique tool name (snake_case).
        description: Human-readable description for the LLM.
        input_schema: Pydantic model class for input validation.
        handler: Async function that executes the tool.
                   Signature: (params: BaseModel, context: dict) -> Any
        category: Optional category for grouping tools.
    """

    name: str
    description: str
    input_schema: type[BaseModel]
    handler: Callable[..., Awaitable[Any]]
    category: str = "general"

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool definition format.

        Returns:
            Tool definition in OpenAI API format.
        """
        schema = self.input_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class ToolRegistry:
    """Registry of all available tools.

    Tools are registered at startup and looked up by name at runtime.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        """Register a tool.

        Args:
            tool: The tool specification.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"Tool registered: {tool.name} ({tool.category})")

    def get(self, name: str) -> ToolSpec | None:
        """Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            ToolSpec if found, None otherwise.
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name.

        Returns:
            True if the tool exists.
        """
        return name in self._tools

    @property
    def tool_names(self) -> list[str]:
        """List of all registered tool names."""
        return list(self._tools.keys())

    @property
    def tools(self) -> list[ToolSpec]:
        """List of all registered tools."""
        return list(self._tools.values())

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Get all tools in OpenAI API format.

        Returns:
            List of tool definitions.
        """
        return [t.to_openai_format() for t in self._tools.values()]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any] | str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments (dict or JSON string).
            context: Optional context passed to the handler.

        Returns:
            The tool's return value.

        Raises:
            ValidationError: If the tool doesn't exist or arguments are invalid.
        """
        tool = self.get(tool_name)
        if tool is None:
            raise ValidationError(f"Unknown tool: {tool_name}")

        # Parse JSON string arguments if needed
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as e:
                raise ValidationError(
                    f"Invalid JSON arguments for tool '{tool_name}': {e}"
                ) from e

        # Validate arguments against schema
        try:
            params = tool.input_schema.model_validate(arguments)
        except Exception as e:
            raise ValidationError(
                f"Invalid arguments for tool '{tool_name}': {e}"
            ) from e

        # Execute handler
        logger.info(f"Executing tool: {tool_name}")
        result = await tool.handler(params, context or {})
        return result


# Global tool registry instance
TOOL_REGISTRY = ToolRegistry()


# =========================================================================
# Built-in tools (registered at import time)
# =========================================================================


class EchoParams(BaseModel):
    """Parameters for the echo tool."""

    message: str = Field(..., description="The message to echo back.")


async def echo_handler(params: EchoParams, context: dict) -> str:
    """Echo back the input message. Useful for testing."""
    return f"Echo: {params.message}"


class GetHelpParams(BaseModel):
    """Parameters for the get_help tool."""

    topic: str | None = Field(default=None, description="Optional topic to get help about.")


async def get_help_handler(params: GetHelpParams, context: dict) -> str:
    """Get help about available tools and how to use them."""
    tools = TOOL_REGISTRY.tools
    lines = ["Available tools:"]
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
    lines.append(
        "\nTo use a tool, specify the tool name and provide the required arguments. "
        "If you can answer the question directly, just provide the final answer."
    )
    if params.topic:
        lines.append(f"\nHelp for topic '{params.topic}': "
                     f"Use the search_stub tool to find more information.")
    return "\n".join(lines)


class SearchStubParams(BaseModel):
    """Parameters for the search stub tool."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query.")
    max_results: int = Field(default=5, ge=1, le=20, description="Max number of results.")


# Fields surfaced to the agent (and shown in the UI's tool-result panel).
_SEARCH_FIELDS = ("id", "title", "authors", "year", "venue", "abstract", "doi", "url", "score")


async def search_stub_handler(params: SearchStubParams, context: dict) -> list[dict]:
    """Search for academic papers over the bundled demo catalog.

    Returns ranked papers with real metadata. A production deployment swaps
    ``search_mock_papers`` for a retrieval client without changing this shape.
    """
    hits = search_mock_papers(params.query, limit=params.max_results)
    return [{k: p.get(k) for k in _SEARCH_FIELDS} for p in hits]


class SummarizeStubParams(BaseModel):
    """Parameters for the summarize stub tool."""

    text: str = Field(..., min_length=10, description="Text to summarize.")
    style: str = Field(default="concise", description="Summary style: concise, detailed, bullet_points")


async def summarize_stub_handler(params: SummarizeStubParams, context: dict) -> str:
    """Summarize text (stub implementation). Returns a short summary."""
    text = params.text
    summary_text = text[:180] + "..." if len(text) > 200 else text

    if params.style == "bullet_points":
        return (
            f"• Key point 1: {summary_text[:80]}\n"
            f"• Key point 2: {summary_text[80:160]}\n"
            f"• Key point 3: Additional context from the source material"
        )
    elif params.style == "detailed":
        return (
            f"Detailed summary of the provided text ({len(text)} chars):\n\n"
            f"The text discusses: {summary_text}\n\n"
            f"Main ideas are captured above. Full text available upon request."
        )
    else:  # concise
        return f"Summary: {summary_text}"


# Register built-in tools
TOOL_REGISTRY.register(ToolSpec(
    name="get_help",
    description="Get help about available tools and how to use them. "
                "Use this when you're unsure what tools are available or how to proceed.",
    input_schema=GetHelpParams,
    handler=get_help_handler,
    category="utility",
))

TOOL_REGISTRY.register(ToolSpec(
    name="echo",
    description="Echo back a message. Useful for testing and debugging.",
    input_schema=EchoParams,
    handler=echo_handler,
    category="utility",
))

TOOL_REGISTRY.register(ToolSpec(
    name="search_stub",
    description="Search for academic papers on a given topic. "
                "Returns a list of paper results with titles, authors, and abstracts.",
    input_schema=SearchStubParams,
    handler=search_stub_handler,
    category="research",
))

TOOL_REGISTRY.register(ToolSpec(
    name="summarize_stub",
    description="Summarize a piece of text. Supports concise, detailed, and bullet point styles.",
    input_schema=SummarizeStubParams,
    handler=summarize_stub_handler,
    category="research",
))
