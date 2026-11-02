"""LangGraph compilation for the agent and the research pipeline.

This package makes LangGraph the core of both flows:

- ``agent.py`` — compiled ReAct ``StateGraph`` (planner → agent ⇄ tools → final).
- ``pipeline.py`` — compiled linear ``StateGraph`` over the 8 pipeline stages.
- ``llm.py`` — LangChain ``BaseChatModel`` adapters over the existing ``LLMClient``.
- ``tools.py`` — ``ToolSpec`` → ``langchain_core.tools`` adapters.
- ``streaming.py`` — LangGraph stream output → the legacy SSE event dicts.
"""
from __future__ import annotations

from app.graphs.agent import build_agent_graph, serialize_agent_state
from app.graphs.llm import LangChainChatModel, RuleBasedChatModel, get_chat_model
from app.graphs.pipeline import (
    build_pipeline_graph,
    default_pipeline_stages,
    serialize_pipeline_state,
)
from app.graphs.streaming import agent_stream_events, pipeline_stream_events

__all__ = [
    "LangChainChatModel",
    "RuleBasedChatModel",
    "agent_stream_events",
    "build_agent_graph",
    "build_pipeline_graph",
    "default_pipeline_stages",
    "get_chat_model",
    "pipeline_stream_events",
    "serialize_agent_state",
    "serialize_pipeline_state",
]
