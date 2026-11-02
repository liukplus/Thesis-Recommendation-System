"""Plan-first agent: breaks the goal into steps before executing.

The planner generates a high-level plan, then the executor follows it.
For the skeleton, the planner uses the LLM to generate a plan.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from app.agent.state import PlanStep
from app.core.logging import get_logger
from app.llm.base import ChatMessage, LLMClient

logger = get_logger(__name__)


class PlanStepSchema(BaseModel):
    """Schema for a single plan step (for structured output)."""

    index: int = Field(..., description="Step number, starting from 1.")
    description: str = Field(..., description="What to do in this step, one sentence.")
    tool: str | None = Field(default=None, description="Tool to use, if any.")


class PlanSchema(BaseModel):
    """Schema for a full plan (for structured output)."""

    steps: list[PlanStepSchema] = Field(..., description="List of plan steps.")


SYSTEM_PROMPT = """You are a research assistant planner. Given a user's goal,
break it down into a sequence of 3-7 concrete steps to achieve the goal.

Available tools:
- run_research: Run the full research pipeline on a question
- get_help: Get help about available tools

Guidelines:
- Each step should be a single clear action
- Steps should build on each other logically
- If a step needs a tool, specify which tool
- The last step should be to synthesize and provide the final answer
- Keep each step description to one sentence

Respond with a JSON object like:
{
  "steps": [
    {"index": 1, "description": "Analyze the query", "tool": null},
    {"index": 2, "description": "Run the research pipeline", "tool": "run_research"},
    {"index": 3, "description": "Provide final answer", "tool": null}
  ]
}"""


class PlanFirstPlanner:
    """Generates a plan before executing the agent loop.

    For the skeleton, we support both:
    1. LLM-based planning (requires configured LLM)
    2. Simple template-based planning (fallback, always works)
    """

    def __init__(self, llm: LLMClient | None = None) -> None:
        """Initialize the planner.

        Args:
            llm: Optional LLM client for smart planning.
                 If None, uses template-based planning.
        """
        self.llm = llm

    async def generate_plan(self, goal: str) -> list[PlanStep]:
        """Generate a plan for the given goal.

        Args:
            goal: The user's goal/query.

        Returns:
            List of PlanStep objects.
        """
        if self.llm:
            try:
                return await self._llm_plan(goal)
            except Exception as e:
                logger.warning(f"LLM planning failed, falling back to template: {e}")

        return self._template_plan(goal)

    async def _llm_plan(self, goal: str) -> list[PlanStep]:
        """Generate a plan using the LLM."""
        assert self.llm is not None

        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=goal),
        ]

        result = await self.llm.chat(
            messages,
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )

        content = result.content.strip()
        # Strip code fences if present
        if content.startswith("```"):
            content = _strip_code_fences(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as parse_error:
            # Try to find JSON in the text
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError("Could not parse plan as JSON") from parse_error

        plan_data = PlanSchema.model_validate(data)
        steps = [
            PlanStep(
                index=s.index,
                description=s.description,
                tool=s.tool,
            )
            for s in plan_data.steps
        ]
        logger.info(f"Generated {len(steps)}-step plan via LLM")
        return steps

    def _template_plan(self, goal: str) -> list[PlanStep]:
        """Generate a simple template-based plan (fallback).

        Works without an LLM. Good for the skeleton/demo.
        """
        goal_lower = goal.lower()
        steps: list[PlanStep] = []

        # Step 1: Understand the query
        steps.append(
            PlanStep(
                index=1,
                description="Analyze the user's query and determine information needs",
                tool=None,
            )
        )

        # Step 2: Run the research pipeline (for research queries)
        is_research = any(
            kw in goal_lower
            for kw in ["paper", "survey", "research", "study", "论文", "综述", "研究"]
        )
        if is_research or len(goal) > 10:
            steps.append(
                PlanStep(
                    index=len(steps) + 1,
                    description="Run the research pipeline to find relevant papers",
                    tool="run_research",
                )
            )

        # Final step: synthesize answer
        steps.append(
            PlanStep(
                index=len(steps) + 1,
                description="Synthesize findings and provide the final answer with citations",
                tool=None,
            )
        )

        logger.info(f"Generated {len(steps)}-step plan via template")
        return steps


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from text."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
