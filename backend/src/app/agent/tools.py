"""Tool registry and base tool specification.

Tools are functions the agent can call. Each tool has:
- name: unique identifier
- description: used by the LLM to decide when to use the tool
- input_schema: Pydantic model describing the arguments
- handler: async function that executes the tool

The TOOL_REGISTRY is the central registry of all available tools.

The agent is a *bounded wrapper* (D2): its single research action is ``run_research``,
which delegates to the deterministic 8-stage pipeline rather than performing free-form
searches itself. ``get_help`` is a harmless meta-tool describing the available tools.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.core.logging import get_logger

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
                raise ValidationError(f"Invalid JSON arguments for tool '{tool_name}': {e}") from e

        # Validate arguments against schema
        try:
            params = tool.input_schema.model_validate(arguments)
        except Exception as e:
            raise ValidationError(f"Invalid arguments for tool '{tool_name}': {e}") from e

        # Execute handler
        logger.info(f"Executing tool: {tool_name}")
        result = await tool.handler(params, context or {})
        return result


# Global tool registry instance
TOOL_REGISTRY = ToolRegistry()


# =========================================================================
# Built-in tools (registered at import time)
# =========================================================================


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
        lines.append(
            f"\nHelp for topic '{params.topic}': Use the run_research tool to find "
            f"and synthesize relevant papers."
        )
    return "\n".join(lines)


class RunResearchParams(BaseModel):
    """Arguments for the ``run_research`` delegate tool."""

    query: str = Field(..., min_length=1, max_length=2000, description="Research question.")


async def run_research_handler(params: RunResearchParams, context: dict) -> dict:
    """Run the deterministic research pipeline and return its typed result.

    This is the agent's single research action: it delegates to the fixed 8-stage
    pipeline (D2) rather than performing free-form searches itself.
    """
    from app.domain.pipeline import PipelineData
    from app.graphs.pipeline import build_pipeline_graph, serialize_pipeline_state

    graph = build_pipeline_graph()
    initial = {"query": params.query, "data": PipelineData(), "stage_results": []}
    state = await graph.ainvoke(initial)
    return serialize_pipeline_state(state)


# Register built-in tools
TOOL_REGISTRY.register(
    ToolSpec(
        name="get_help",
        description="Get help about available tools and how to use them. "
        "Use this when you're unsure what tools are available or how to proceed.",
        input_schema=GetHelpParams,
        handler=get_help_handler,
        category="utility",
    )
)

TOOL_REGISTRY.register(
    ToolSpec(
        name="run_research",
        description="Run the full research pipeline on a question: parse the query, "
        "recall papers, fuse and rerank them, extract evidence, generate a cited survey, "
        "verify citations, and export. Returns the answer plus ranked papers.",
        input_schema=RunResearchParams,
        handler=run_research_handler,
        category="research",
    )
)
