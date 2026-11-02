"""Agent API endpoints.

Endpoints for running the ReAct agent, planning, and streaming.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.planner import PlanFirstPlanner
from app.agent.tools import TOOL_REGISTRY
from app.api.deps import LLMClientDep, SettingsDep
from app.core.ids import ensure_trace_id, new_id
from app.core.logging import get_logger
from app.graphs.agent import build_agent_graph, serialize_agent_state
from app.graphs.llm import get_chat_model
from app.graphs.streaming import agent_stream_events

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    """Request to run the agent."""

    query: str = Field(..., min_length=1, max_length=2000, description="User query/goal")
    max_steps: int = Field(default=5, ge=1, le=20, description="Max agent steps")
    max_total_tokens: int = Field(
        default=0,
        ge=0,
        description="Cumulative token budget guardrail (0 = unlimited)",
    )
    plan_first: bool = Field(default=True, description="Generate a plan first")
    stream: bool = Field(default=False, description="Stream events via SSE")


class AgentRunResponse(BaseModel):
    """Response from an agent run."""

    task_id: str
    status: str
    final_answer: str = ""
    steps: int
    tool_calls: list[dict] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    plan: list[dict] = Field(default_factory=list)
    error: str | None = None


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    req: AgentRunRequest,
    settings: SettingsDep,
    llm: LLMClientDep,
) -> AgentRunResponse:
    """Run the agent synchronously and return the final result."""
    ensure_trace_id()
    logger.info(f"Agent run requested: {req.query[:80]}...")

    model = get_chat_model(llm)
    graph = build_agent_graph(
        model,
        planner=PlanFirstPlanner(llm=llm),
        max_steps=req.max_steps,
        max_total_tokens=req.max_total_tokens,
        plan_first=req.plan_first,
    )

    initial = {"goal": req.query, "messages": [], "task_id": new_id("agent")}
    state = await graph.ainvoke(
        initial,
        config={"recursion_limit": req.max_steps * 2 + 4},
    )

    return AgentRunResponse(**serialize_agent_state(state))


@router.post("/run-stream")
async def run_agent_stream(
    req: AgentRunRequest,
    settings: SettingsDep,
    llm: LLMClientDep,
) -> StreamingResponse:
    """Run the agent with SSE streaming.

    Events:
    - start: agent started
    - plan: plan generated (if plan_first)
    - thought: agent's thought/step
    - tool_call: agent is calling a tool
    - tool_result: tool returned a result
    - tool_error: tool call failed
    - final_answer: agent produced final answer
    - error: agent encountered a fatal error
    - end: agent finished
    """
    ensure_trace_id()

    model = get_chat_model(llm)
    graph = build_agent_graph(
        model,
        planner=PlanFirstPlanner(llm=llm),
        max_steps=req.max_steps,
        max_total_tokens=req.max_total_tokens,
        plan_first=req.plan_first,
    )

    initial = {"goal": req.query, "messages": [], "task_id": new_id("agent")}

    config = {"recursion_limit": req.max_steps * 2 + 4}

    async def event_generator():
        """Generate SSE events from the compiled agent graph."""
        async for event in agent_stream_events(graph, initial, config=config):
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/plan")
async def plan_only(
    req: AgentRunRequest,
    settings: SettingsDep,
    llm: LLMClientDep,
) -> dict:
    """Generate a plan without executing it.

    Returns the plan steps only.
    """
    ensure_trace_id()
    planner = PlanFirstPlanner(llm=llm)
    steps = await planner.generate_plan(req.query)

    return {
        "query": req.query,
        "steps": [s.to_dict() for s in steps],
    }


@router.get("/tools")
async def list_tools() -> dict:
    """List all available agent tools."""
    tools = []
    for tool in TOOL_REGISTRY.tools:
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "parameters": tool.input_schema.model_json_schema(),
        })

    return {"tools": tools, "total": len(tools)}
