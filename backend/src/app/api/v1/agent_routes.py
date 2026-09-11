"""Agent API endpoints.

Endpoints for running the ReAct agent, planning, and streaming.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import LLMClientDep, SettingsDep
from app.agent.loop import AgentRuntime
from app.agent.planner import PlanFirstPlanner
from app.agent.tools import TOOL_REGISTRY
from app.core.ids import ensure_trace_id
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    """Request to run the agent."""

    query: str = Field(..., min_length=1, max_length=2000, description="User query/goal")
    max_steps: int = Field(default=5, ge=1, le=20, description="Max agent steps")
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
    error: Optional[str] = None


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    req: AgentRunRequest,
    settings: SettingsDep,
    llm: LLMClientDep,
) -> AgentRunResponse:
    """Run the agent synchronously and return the final result."""
    ensure_trace_id()
    logger.info(f"Agent run requested: {req.query[:80]}...")

    runtime = AgentRuntime(
        llm=llm,
        tools=TOOL_REGISTRY,
        max_steps=req.max_steps,
        plan_first=req.plan_first,
    )

    state = await runtime.run(req.query)

    return AgentRunResponse(
        task_id=state.task_id,
        status=state.status,
        final_answer=state.final_answer,
        steps=state.step_idx,
        tool_calls=[
            {"name": tc.name, "arguments": tc.arguments, "error": tc.error}
            for tc in state.tool_calls
        ],
        usage={
            "prompt_tokens": state.usage.prompt_tokens,
            "completion_tokens": state.usage.completion_tokens,
            "total_tokens": state.usage.total_tokens,
        },
        plan=[s.to_dict() for s in state.plan],
        error=state.error,
    )


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
    queue: asyncio.Queue[str] = asyncio.Queue()

    async def event_callback(event: dict):
        """Queue event for SSE streaming."""
        await queue.put(json.dumps(event, ensure_ascii=False, default=str))

    async def event_generator():
        """Generate SSE events from the agent run."""
        runtime = AgentRuntime(
            llm=llm,
            tools=TOOL_REGISTRY,
            max_steps=req.max_steps,
            plan_first=req.plan_first,
        )

        # Start the agent in the background
        task = asyncio.create_task(
            runtime.run(req.query, event_callback=event_callback)
        )

        # Stream events
        while True:
            if task.done() and queue.empty():
                break

            try:
                event_data = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f"data: {event_data}\n\n"
            except asyncio.TimeoutError:
                # Check if task is done
                if task.done():
                    break
                continue

        # Ensure task is complete
        await task
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
