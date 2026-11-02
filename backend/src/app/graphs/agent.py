"""LangGraph-compiled ReAct agent.

Replaces ``app/agent/loop.py::AgentRuntime`` with a compiled ``StateGraph`` whose
nodes are the same steps (plan -> think ⇄ execute-tool -> final answer) while keeping
the external contract (event names + JSON field shapes) intact.

State channels:
- ``messages`` uses ``add_messages`` (append-merge of LangChain messages).
- ``usage`` uses a merge reducer (cumulative token counts).
- everything else is last-write-wins.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.agent.guardrails import GuardrailController
from app.agent.planner import PlanFirstPlanner
from app.agent.tools import TOOL_REGISTRY
from app.graphs.tools import to_langchain_tools, to_openai_format

REACT_SYSTEM_PROMPT = """You are a helpful research assistant agent. You help users find
and understand academic papers.

You have access to the following tools:
{tool_descriptions}

## How to respond

Use a tool to gather information when needed. When you have enough information
to answer the user's question, provide your final answer directly without
calling any tools.

For each step:
1. Think about what you need to do next
2. If you need more information, call a tool
3. When you have a complete answer, provide it as your final response

Your final answer should be comprehensive, well-structured, and cite your sources.
"""

_USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


def _merge_usage(left: Any, right: Any) -> dict[str, int]:
    """Merge two usage dicts by summing token counts."""
    merged: dict[str, int] = {}
    for key in _USAGE_KEYS:
        merged[key] = int((left or {}).get(key, 0) or 0) + int((right or {}).get(key, 0) or 0)
    return merged


class AgentState(TypedDict, total=False):
    """State for the compiled agent graph."""

    messages: Annotated[list, add_messages]
    goal: str
    task_id: str
    plan: list[dict]
    steps: int
    status: str  # running | completed | failed | cancelled
    final_answer: str
    error: str
    usage: Annotated[dict, _merge_usage]


def _build_system_prompt(tools: list[BaseTool]) -> str:
    """Build the system prompt from the available tool descriptions."""
    lines = [f"- **{tool.name}**: {tool.description}" for tool in tools]
    return REACT_SYSTEM_PROMPT.format(tool_descriptions="\n".join(lines))


def _usage_delta(ai_msg: AIMessage) -> dict[str, int]:
    """Extract token usage from a LangChain ``AIMessage``.

    ``usage_metadata`` is a plain dict at runtime (``{"input_tokens", ...}``),
    not an object, so it must be indexed rather than read with ``getattr``.
    """
    usage = getattr(ai_msg, "usage_metadata", None) or {}

    def _read(key: str) -> int:
        if isinstance(usage, dict):
            return int(usage.get(key, 0) or 0)
        return int(getattr(usage, key, 0) or 0)

    return {
        "prompt_tokens": _read("input_tokens"),
        "completion_tokens": _read("output_tokens"),
        "total_tokens": _read("total_tokens"),
    }


def _to_str(content: Any) -> str:
    """Coerce LangChain message content (``str | list[..]``) to plain text."""
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
    return str(content or "")


def _extract_final_answer(messages: list) -> str:
    """Return the content of the most recent tool-free assistant message."""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            return _to_str(message.content)
    return ""


def _guardrail_state(state: AgentState) -> SimpleNamespace:
    """Adapt graph state to the fields ``GuardrailController.check_all`` reads.

    The controller reads ``state.step_idx`` and ``state.usage.total_tokens``; the
    graph carries those as ``steps`` and a cumulative ``usage`` dict. The other two
    guardrails (loop detection, consecutive errors) read the controller's own
    recorded fingerprints/counters, not the state.
    """
    usage = state.get("usage") or {}
    return SimpleNamespace(
        step_idx=int(state.get("steps", 0) or 0),
        usage=SimpleNamespace(total_tokens=int(usage.get("total_tokens", 0) or 0)),
    )


def build_agent_graph(
    model: BaseChatModel,
    *,
    tools: list[BaseTool] | None = None,
    planner: PlanFirstPlanner | None = None,
    max_steps: int = 5,
    max_total_tokens: int = 0,
    loop_threshold: int = 3,
    max_consecutive_errors: int = 3,
    plan_first: bool = True,
):
    """Compile the ReAct agent into a ``StateGraph``.

    Args:
        model: LangChain chat model (wraps the ``LLMClient``).
        tools: Optional tool list; defaults to ``TOOL_REGISTRY`` wrapped as LangChain tools.
        planner: Optional ``PlanFirstPlanner``; defaults to a template-based planner.
        max_steps: Hard cap on agent think/act cycles.
        max_total_tokens: Token budget (0 = unlimited).
        loop_threshold: Identical tool calls before the loop guardrail trips.
        max_consecutive_errors: Consecutive tool errors before the circuit breaker trips.
        plan_first: Emit a plan before the first thought.

    Returns:
        A compiled LangGraph state graph.
    """
    if tools is None:
        tools = to_langchain_tools(TOOL_REGISTRY)
    tool_map = {tool.name: tool for tool in tools}
    tools_openai = to_openai_format(tools)
    planner = planner or PlanFirstPlanner(llm=None)
    system_prompt = _build_system_prompt(tools)

    # One controller per compiled graph. Callers build a fresh graph per request
    # (see the agent routes), so the controller's loop/error state is request-scoped.
    guardrails = GuardrailController(
        max_steps=max_steps,
        max_total_tokens=max_total_tokens,
        loop_threshold=loop_threshold,
        max_consecutive_errors=max_consecutive_errors,
    )

    async def planner_node(state: AgentState) -> dict[str, Any]:
        """Generate the plan and emit the ``plan`` event."""
        writer = get_stream_writer()
        goal = state.get("goal", "")
        plan_steps = await planner.generate_plan(goal)
        plan_dicts = [step.to_dict() for step in plan_steps]
        writer({"type": "plan", "steps": plan_dicts})
        return {"plan": plan_dicts}

    async def agent_node(state: AgentState) -> dict[str, Any]:
        """One think step: enforce guardrails, then call the model; emit ``thought``."""
        writer = get_stream_writer()
        steps = int(state.get("steps", 0) or 0)

        guardrail = guardrails.check_all(_guardrail_state(state))
        if guardrail.should_stop:
            return {"status": "failed", "error": guardrail.reason}

        goal = state.get("goal", "")
        history = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=goal),
            *(state.get("messages") or []),
        ]

        try:
            ai_msg = await model.bind(tools=tools_openai).ainvoke(history)
        except Exception as e:  # noqa: BLE001 - parity with the old loop: fail the run
            # ``route`` sends failed runs to ``final_node``, which emits the single
            # terminal ``error`` event; do not emit from here as well.
            return {"status": "failed", "error": f"LLM error: {e}"}

        writer({
            "type": "thought",
            "step": steps + 1,
            "content": _to_str(ai_msg.content),
        })
        return {
            "messages": [ai_msg],
            "steps": steps + 1,
            "usage": _usage_delta(ai_msg),
        }

    async def tool_node(state: AgentState) -> dict[str, Any]:
        """Execute the tool calls in the last assistant message; emit tool events."""
        writer = get_stream_writer()
        step = int(state.get("steps", 0) or 0)
        messages = state.get("messages") or []
        last = messages[-1] if messages else None

        tool_messages: list = []
        if isinstance(last, AIMessage):
            for tc in getattr(last, "tool_calls", None) or []:
                name = tc.get("name", "")
                args = tc.get("args", {})
                call_id = tc.get("id", "")
                writer({
                    "type": "tool_call",
                    "tool": name,
                    "arguments": args,
                    "call_id": call_id,
                    "step": step,
                })

                tool = tool_map.get(name)
                guardrails.record_tool_call(name, args)
                try:
                    if tool is None:
                        raise ValueError(f"Unknown tool: {name}")
                    result = await tool.ainvoke(args)
                    content = json.dumps(result, ensure_ascii=False, default=str)
                    writer({
                        "type": "tool_result",
                        "tool": name,
                        "result": result,
                        "call_id": call_id,
                        "step": step,
                    })
                    guardrails.record_tool_success()
                    tool_messages.append(
                        ToolMessage(content=content, tool_call_id=call_id, name=name)
                    )
                except Exception as e:  # noqa: BLE001 - mirror legacy per-tool error handling
                    writer({
                        "type": "tool_error",
                        "tool": name,
                        "error": str(e),
                        "call_id": call_id,
                        "step": step,
                    })
                    guardrails.record_tool_error()
                    tool_messages.append(
                        ToolMessage(content=f"Error: {e}", tool_call_id=call_id, name=name)
                    )

        return {"messages": tool_messages}

    async def final_node(state: AgentState) -> dict[str, Any]:
        """Set the final answer (or error) and emit the terminal event."""
        writer = get_stream_writer()
        if state.get("status") == "failed":
            writer({"type": "error", "error": state.get("error") or "agent failed"})
            return {}
        answer = _extract_final_answer(state.get("messages") or [])
        writer({"type": "final_answer", "content": answer})
        return {"status": "completed", "final_answer": answer}

    def route(state: AgentState) -> str:
        """Route the agent: to tools if a tool call was requested, else finalize."""
        if state.get("status") in ("failed", "cancelled"):
            return "final"
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return "final"

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("final", final_node)

    if plan_first:
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "agent")
    else:
        graph.add_edge(START, "agent")

    graph.add_conditional_edges("agent", route, {"tools": "tools", "final": "final"})
    graph.add_edge("tools", "agent")
    graph.add_edge("final", END)

    return graph.compile()


def _derive_tool_calls(messages: list) -> list[dict[str, Any]]:
    """Map assistant tool calls to ``{name, arguments, error}`` (legacy shape)."""
    results_by_id: dict[str, str] = {}
    for message in messages:
        if isinstance(message, ToolMessage) and message.tool_call_id:
            results_by_id[message.tool_call_id] = _to_str(message.content)

    tool_calls: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for tc in getattr(message, "tool_calls", None) or []:
            content = results_by_id.get(tc.get("id"))
            error: str | None = None
            if isinstance(content, str) and content.startswith("Error: "):
                error = content[len("Error: "):]
            tool_calls.append({
                "name": tc.get("name", ""),
                "arguments": tc.get("args", {}),
                "error": error,
            })
    return tool_calls


def serialize_agent_state(state: dict[str, Any]) -> dict[str, Any]:
    """Map a compiled-agent final state to the ``AgentRunResponse`` field shape."""
    usage = state.get("usage") or {}
    return {
        "task_id": state.get("task_id", ""),
        "status": state.get("status", "completed"),
        "final_answer": state.get("final_answer", ""),
        "steps": int(state.get("steps", 0) or 0),
        "tool_calls": _derive_tool_calls(state.get("messages") or []),
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        },
        "plan": state.get("plan") or [],
        "error": state.get("error"),
    }
