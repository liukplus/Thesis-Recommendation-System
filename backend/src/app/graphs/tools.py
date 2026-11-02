"""Adapt ``ToolSpec`` -> ``langchain_core.tools``.

The ``ToolRegistry`` remains the source of truth (``/agent/tools`` keeps working off
it); this module wraps each ``ToolSpec`` into a LangChain ``StructuredTool`` so the
compiled agent graph can route and invoke tools through ``bind(tools=[...])``.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from app.agent.tools import ToolRegistry, ToolSpec


def to_langchain_tools(registry: ToolRegistry) -> list[BaseTool]:
    """Wrap every tool in ``registry`` as a LangChain ``StructuredTool``."""
    return [_build_tool(spec) for spec in registry.tools]


def _build_tool(spec: ToolSpec) -> BaseTool:
    """Build a single ``StructuredTool`` from a ``ToolSpec``.

    ``StructuredTool.from_function(coroutine=...)`` forwards the *validated field
    values* as ``**kwargs`` (not a pydantic instance), so we rebuild the schema
    object before delegating to ``spec.handler(params, context={})``.
    """

    async def _run(**kwargs: Any) -> Any:
        params = spec.input_schema(**kwargs)
        return await spec.handler(params, {})

    return StructuredTool.from_function(
        name=spec.name,
        description=spec.description,
        args_schema=spec.input_schema,
        coroutine=_run,
    )


def to_openai_format(tools: list[BaseTool]) -> list[dict[str, Any]]:
    """Convert LangChain tools to the OpenAI tool-definition format.

    Used to pass tools to ``model.bind(tools=[...])`` so the underlying
    ``LLMClient.chat(tools=...)`` receives the same wire format it always has.
    """
    definitions: list[dict[str, Any]] = []
    for tool in tools:
        schema: dict[str, Any] = {}
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is not None:
            schema = args_schema.model_json_schema()
        definitions.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": schema,
            },
        })
    return definitions
