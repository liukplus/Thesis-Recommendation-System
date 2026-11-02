"""Structured output support for LLM calls.

Provides `complete_structured()` which requests JSON output from the LLM
and validates it against a Pydantic model. Includes one automatic repair
retry if validation fails.
"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import LLMValidationError
from app.core.logging import get_logger
from app.llm.base import ChatMessage, ChatResult, LLMClient

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


async def complete_structured(
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
    output_model: type[T],
    *,
    max_retries: int = 1,
    **chat_kwargs,
) -> tuple[T, ChatResult]:
    """Request structured JSON output from the LLM and validate against a Pydantic model.

    If validation fails, automatically retries once with the error message.

    Args:
        client: The LLM client to use.
        system_prompt: System prompt for the LLM.
        user_prompt: User prompt / query.
        output_model: Pydantic model class to validate against.
        max_retries: Number of repair retries on validation failure (default: 1).
        **chat_kwargs: Additional kwargs passed to client.chat().

    Returns:
        Tuple of (parsed_model_instance, full_chat_result).

    Raises:
        LLMValidationError: If validation fails even after retries.
    """
    schema_desc = _format_schema_description(output_model)
    enhanced_system = (
        f"{system_prompt}\n\n"
        "You must respond with valid JSON matching this schema:\n"
        f"{schema_desc}\n\n"
        "Return ONLY the JSON object, no markdown, no explanation, no code fences."
    )

    messages = [
        ChatMessage(role="system", content=enhanced_system),
        ChatMessage(role="user", content=user_prompt),
    ]

    last_result: ChatResult | None = None
    last_error: ValidationError | None = None

    for attempt in range(max_retries + 1):
        result = await client.chat(
            messages,
            response_format={"type": "json_object"},
            **chat_kwargs,
        )
        last_result = result

        content = result.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = _strip_code_fences(content)

        try:
            parsed = output_model.model_validate_json(content)
            return parsed, result
        except ValidationError as e:
            last_error = e
            logger.warning(
                f"Structured output validation failed (attempt {attempt + 1}): "
                f"{e.errors()[:3]}"
            )
            if attempt < max_retries:
                # Add the error as a user message for the retry
                messages.append(
                    ChatMessage(role="assistant", content=result.content)
                )
                messages.append(
                    ChatMessage(
                        role="user",
                        content=(
                            "Your previous response failed validation. "
                            f"Errors: {e.errors()}\n"
                            "Please fix and return valid JSON matching the schema exactly."
                        ),
                    )
                )

    raise LLMValidationError(
        f"Failed to get valid structured output after {max_retries + 1} attempts. "
        f"Last error: {last_error.errors() if last_error else 'unknown'}",
        details={
            "last_response": last_result.content if last_result else "",
            "validation_errors": last_error.errors() if last_error else [],
        },
    )


def _format_schema_description(model: type[BaseModel]) -> str:
    """Format a Pydantic model's JSON schema as a readable description."""
    schema = model.model_json_schema()
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    lines = []
    for name, props in properties.items():
        type_str = props.get("type", "any")
        desc = props.get("description", "")
        req = " (required)" if name in required else " (optional)"
        lines.append(f"  - {name}: {type_str}{req} — {desc}")
    return "\n".join(lines)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from text."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
