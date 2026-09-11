"""ReAct agent loop.

The agent alternates between:
1. Thought: LLM decides what to do (or gives final answer)
2. Action: If tool call selected, execute the tool
3. Observation: Tool result is added to the conversation

The loop continues until:
- The LLM provides a final answer (no tool call)
- Max steps reached
- Token budget exceeded
- Loop detected
- Cancelled

For the skeleton, if no LLM is configured, it uses a simple rule-based fallback
that still exercises the full ReAct loop architecture.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Optional

from app.core import cat_integration
from app.core.exceptions import AppError
from app.core.ids import ensure_trace_id, set_trace_id
from app.core.logging import get_logger
from app.agent.guardrails import GuardrailController
from app.agent.planner import PlanFirstPlanner
from app.agent.state import AgentState, ToolCall
from app.agent.tools import TOOL_REGISTRY, ToolRegistry
from app.llm.base import ChatMessage, ChatResult, LLMClient

logger = get_logger(__name__)

# Event types for streaming callbacks
AgentEvent = dict[str, Any]
EventCallback = Callable[[AgentEvent], Awaitable[None] | None]

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


class AgentRuntime:
    """ReAct agent runtime.

    Manages the agent loop: thought → action → observation → repeat.

    Args:
        llm: LLM client (optional; if None, uses rule-based fallback).
        tools: Tool registry (defaults to global TOOL_REGISTRY).
        max_steps: Maximum steps (hard cap).
        max_total_tokens: Maximum total tokens (0 = unlimited).
        plan_first: Whether to generate a plan before executing.
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        tools: Optional[ToolRegistry] = None,
        max_steps: int = 5,
        max_total_tokens: int = 0,
        plan_first: bool = True,
    ) -> None:
        self.llm = llm
        self.tools = tools or TOOL_REGISTRY
        self.max_steps = max_steps
        self.max_total_tokens = max_total_tokens
        self.plan_first = plan_first
        self.planner = PlanFirstPlanner(llm=llm)

    async def run(
        self,
        goal: str,
        *,
        event_callback: Optional[EventCallback] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AgentState:
        """Run the agent on a goal.

        Args:
            goal: The user's goal/query.
            event_callback: Optional callback for streaming events.
            cancel_event: Optional asyncio.Event to cancel the run.

        Returns:
            Final AgentState.
        """
        state = AgentState(
            goal=goal,
            max_steps=self.max_steps,
            status="running",
        )
        state.trace_id = ensure_trace_id()
        set_trace_id(state.trace_id)

        guardrails = GuardrailController(
            max_steps=self.max_steps,
            max_total_tokens=self.max_total_tokens,
        )

        # CAT: agent start
        cat_integration.log_event("Agent", "start", data=f"goal={goal[:80]}...")
        cat_integration.metric("agent.run").count()

        logger.info(f"Agent started: {goal[:80]}...")
        await self._emit(event_callback, {"type": "start", "state": state.to_dict()})

        # Plan-first mode
        if self.plan_first:
            await self._do_plan(state, event_callback)

        # Initialize messages
        system_msg = self._build_system_prompt()
        state.add_message(ChatMessage(role="system", content=system_msg))
        state.add_message(ChatMessage(role="user", content=goal))

        # Main ReAct loop
        while not state.is_finished:
            # Check cancellation
            if cancel_event and cancel_event.is_set():
                state.mark_cancelled()
                await self._emit(event_callback, {"type": "cancel", "state": state.to_dict()})
                break

            # Check guardrails
            gr_result = guardrails.check_all(state)
            if gr_result.should_stop:
                cat_integration.log_event(
                    "Agent",
                    "guardrail_triggered",
                    status=cat_integration.CAT_ERROR,
                    data=f"reason={gr_result.reason}",
                )
                state.mark_failed(f"Guardrail triggered: {gr_result.reason}")
                await self._emit(event_callback, {
                    "type": "error",
                    "error": gr_result.reason,
                    "level": gr_result.level,
                    "state": state.to_dict(),
                })
                break

            # Step 1: Thought (LLM decides what to do)
            try:
                result = await self._think(state)
            except Exception as e:
                state.mark_failed(f"LLM error: {e}")
                await self._emit(event_callback, {
                    "type": "error",
                    "error": str(e),
                    "state": state.to_dict(),
                })
                break

            state.increment_step()
            state.add_usage(result.usage)

            await self._emit(event_callback, {
                "type": "thought",
                "step": state.step_idx,
                "content": result.content,
                "state": state.to_dict(),
            })

            # Step 2: Check if we're done (no tool calls = final answer)
            if not result.tool_calls:
                state.mark_completed(result.content)
                await self._emit(event_callback, {
                    "type": "final_answer",
                    "content": result.content,
                    "state": state.to_dict(),
                })
                break

            # Step 3: Execute tool calls
            for tc_data in result.tool_calls:
                if cancel_event and cancel_event.is_set():
                    break

                tool_call = await self._execute_tool_call(
                    state, tc_data, guardrails, event_callback
                )

            # Add assistant message with tool calls
            state.add_message(ChatMessage(
                role="assistant",
                content=result.content,
                tool_calls=result.tool_calls,
            ))

        if not state.is_finished:
            state.mark_completed("")

        # CAT: agent end
        cat_integration.log_event(
            "Agent",
            state.status,
            data=f"steps={state.step_idx}, tokens={state.usage.total_tokens}",
        )
        cat_integration.metric("agent.steps").count(state.step_idx)
        cat_integration.metric("agent.tokens").duration(state.usage.total_tokens)

        logger.info(
            f"Agent {state.status}: {state.step_idx} steps, "
            f"{state.usage.total_tokens} tokens"
        )
        await self._emit(event_callback, {"type": "end", "state": state.to_dict()})

        return state

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    async def _think(self, state: AgentState) -> ChatResult:
        """Step 1: Get the LLM's next action/thought."""
        if self.llm:
            return await self._llm_think(state)
        else:
            return self._rule_based_think(state)

    async def _llm_think(self, state: AgentState) -> ChatResult:
        """Use LLM to decide the next action."""
        assert self.llm is not None
        tools = self.tools.to_openai_format()

        result = await self.llm.chat(
            state.messages,
            tools=tools,
            temperature=0.2,
            max_tokens=2000,
        )
        return result

    def _rule_based_think(self, state: AgentState) -> ChatResult:
        """Rule-based fallback when no LLM is configured.

        Still exercises the full ReAct loop architecture.
        Decides based on conversation state what to do next.
        """
        from app.llm.base import Usage

        # If this is the first step and we have a goal, search for papers
        if state.step_idx == 0:
            # Check if goal looks like a research query
            goal_lower = state.goal.lower()
            is_research = any(
                kw in goal_lower for kw in
                ["paper", "survey", "research", "study", "论文", "综述", "研究",
                 "what", "how", "why", "explain", "什么", "怎么", "如何"]
            )

            if is_research and self.tools.has("search_stub"):
                # Call search tool
                return ChatResult(
                    content=f"I need to search for information about '{state.goal}'. "
                            f"Let me look for relevant papers first.",
                    model="rule-based",
                    usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    tool_calls=[{
                        "id": "call_rule_001",
                        "type": "function",
                        "function": {
                            "name": "search_stub",
                            "arguments": json.dumps({
                                "query": state.goal,
                                "max_results": 5,
                            }),
                        },
                    }],
                    finish_reason="tool_calls",
                )

            # Simple direct answer
            return ChatResult(
                content=f"Hello! I'm your research assistant. You asked about: {state.goal}\n\n"
                        f"I found some relevant information for you. Since this is a demo "
                        f"running without an LLM backend, I'll provide a template response.\n\n"
                        f"**Key points:**\n"
                        f"- You can configure an LLM provider in settings to enable "
                        f"full AI-powered research assistance\n"
                        f"- The system supports multi-step reasoning with tools\n"
                        f"- Try searching for specific research topics\n\n"
                        f"Let me know if you'd like to explore a specific area further!",
                model="rule-based",
                usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                finish_reason="stop",
            )

        # After a tool call, provide final answer
        if state.tool_calls:
            last_tool = state.tool_calls[-1]
            result_text = str(last_tool.result)

            if last_tool.name == "search_stub":
                # Format search results as a nice answer
                papers = last_tool.result if isinstance(last_tool.result, list) else []
                answer_lines = [
                    f"Here's what I found about **{state.goal}**:\n",
                    f"I found {len(papers)} relevant papers. Here are the top results:\n",
                ]
                for i, p in enumerate(papers[:3], 1):
                    answer_lines.append(
                        f"{i}. **{p.get('title', 'Untitled')}**\n"
                        f"   - Authors: {p.get('authors', 'Unknown')}\n"
                        f"   - Venue: {p.get('venue', '')} ({p.get('year', '')})\n"
                        f"   - Score: {p.get('score', 'N/A')}\n"
                        f"   - {p.get('abstract', '')[:150]}...\n"
                    )
                answer_lines.append(
                    "\nThese are demo results from the stub search tool. "
                    "With a real LLM and paper database, you'd get "
                    "comprehensive, cited answers based on actual research literature."
                )
                answer_text = "\n".join(answer_lines)
            else:
                answer_text = f"Here's the result from {last_tool.name}: {result_text[:500]}"

            return ChatResult(
                content=answer_text,
                model="rule-based",
                usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                finish_reason="stop",
            )

        # Default: end the loop
        return ChatResult(
            content="I've completed my analysis. Let me know if you need anything else!",
            model="rule-based",
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            finish_reason="stop",
        )

    async def _do_plan(
        self,
        state: AgentState,
        event_callback: Optional[EventCallback],
    ) -> None:
        """Generate a plan for the agent run."""
        await self._emit(event_callback, {"type": "plan_start", "goal": state.goal})

        plan_steps = await self.planner.generate_plan(state.goal)
        state.plan = plan_steps
        state.plan_text = "\n".join(
            f"{s.index}. {s.description}" + (f" [{s.tool}]" if s.tool else "")
            for s in plan_steps
        )

        await self._emit(event_callback, {
            "type": "plan",
            "steps": [s.to_dict() for s in plan_steps],
            "state": state.to_dict(),
        })
        logger.info(f"Plan generated: {len(plan_steps)} steps")

    async def _execute_tool_call(
        self,
        state: AgentState,
        tc_data: dict[str, Any],
        guardrails: GuardrailController,
        event_callback: Optional[EventCallback],
    ) -> ToolCall:
        """Execute a single tool call and record it."""
        call_id = tc_data.get("id", "unknown")
        func = tc_data.get("function", {})
        tool_name = func.get("name", "unknown")
        args_str = func.get("arguments", "{}")

        # Parse arguments
        try:
            arguments = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            arguments = {}

        tool_call = ToolCall(
            call_id=call_id,
            name=tool_name,
            arguments=arguments,
        )
        state.add_tool_call(tool_call)
        guardrails.record_tool_call(tool_name, arguments)

        await self._emit(event_callback, {
            "type": "tool_call",
            "tool": tool_name,
            "arguments": arguments,
            "call_id": call_id,
            "step": state.step_idx,
            "state": state.to_dict(),
        })

        # Execute the tool
        try:
            result = await self.tools.execute(
                tool_name,
                arguments,
                context={"state": state, "goal": state.goal},
            )
            tool_call.result = result
            tool_call.finished_at = _utcnow()
            guardrails.record_tool_success()

            # CAT: tool call success
            cat_integration.log_event(
                "Agent",
                f"tool_success:{tool_name}",
                data=f"step={state.step_idx}",
            )
            cat_integration.metric("agent.tool.success").count()

            # Add tool response to messages
            state.add_message(ChatMessage(
                role="tool",
                content=json.dumps(result, ensure_ascii=False, default=str),
                tool_call_id=call_id,
                name=tool_name,
            ))

            await self._emit(event_callback, {
                "type": "tool_result",
                "tool": tool_name,
                "result": result,
                "call_id": call_id,
                "step": state.step_idx,
                "state": state.to_dict(),
            })

        except Exception as e:
            error_msg = str(e)
            tool_call.error = error_msg
            tool_call.finished_at = _utcnow()
            guardrails.record_tool_error()

            # CAT: tool call error
            cat_integration.log_event(
                "Agent",
                f"tool_error:{tool_name}",
                status=cat_integration.CAT_ERROR,
                data=f"step={state.step_idx}, error={error_msg[:100]}",
            )
            cat_integration.metric("agent.tool.error").count()

            # Add error as tool response
            state.add_message(ChatMessage(
                role="tool",
                content=f"Error: {error_msg}",
                tool_call_id=call_id,
                name=tool_name,
            ))

            await self._emit(event_callback, {
                "type": "tool_error",
                "tool": tool_name,
                "error": error_msg,
                "call_id": call_id,
                "step": state.step_idx,
                "state": state.to_dict(),
            })

        return tool_call

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        tool_descriptions = []
        for tool in self.tools.tools:
            tool_descriptions.append(f"- **{tool.name}**: {tool.description}")

        tools_text = "\n".join(tool_descriptions)
        return REACT_SYSTEM_PROMPT.format(tool_descriptions=tools_text)

    async def _emit(
        self,
        callback: Optional[EventCallback],
        event: AgentEvent,
    ) -> None:
        """Emit an event to the callback if provided."""
        if callback is None:
            return
        try:
            result = callback(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.warning(f"Event callback error: {e}")


def _utcnow():
    """Get current UTC datetime."""
    from datetime import datetime
    return datetime.utcnow()
