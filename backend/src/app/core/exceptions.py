"""Exception hierarchy for the application.

All custom exceptions inherit from AppError.
The hierarchy lets callers catch at different granularity levels.
"""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all application errors.

    Attributes:
        code: Machine-readable error code.
        message: Human-readable error message.
        details: Optional structured details about the error.
    """

    code: str = "app_error"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize error to a dictionary for JSON responses."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# ---------------------------------------------------------------------------
# Retryable errors - transient failures, safe to retry
# ---------------------------------------------------------------------------


class RetryableError(AppError):
    """Errors that are likely transient - retrying may succeed."""

    code = "retryable_error"
    status_code = 503


class TimeoutError(RetryableError):
    """Operation timed out."""

    code = "timeout"
    status_code = 504


class RateLimitError(RetryableError):
    """Rate limited by an external service."""

    code = "rate_limited"
    status_code = 429

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after = retry_after


class ServiceUnavailableError(RetryableError):
    """External service is unavailable (5xx)."""

    code = "service_unavailable"
    status_code = 503


# ---------------------------------------------------------------------------
# Non-retryable errors - permanent failures, retrying won't help
# ---------------------------------------------------------------------------


class NonRetryableError(AppError):
    """Errors that are permanent - retrying won't help."""

    code = "non_retryable_error"
    status_code = 400


class ValidationError(NonRetryableError):
    """Input validation failed."""

    code = "validation_error"
    status_code = 400


class NotFoundError(NonRetryableError):
    """Requested resource was not found."""

    code = "not_found"
    status_code = 404


class AuthenticationError(NonRetryableError):
    """Authentication required or failed."""

    code = "unauthenticated"
    status_code = 401


class AuthorizationError(NonRetryableError):
    """User doesn't have permission for this action."""

    code = "forbidden"
    status_code = 403


class BadRequestError(NonRetryableError):
    """Malformed or invalid request."""

    code = "bad_request"
    status_code = 400


# ---------------------------------------------------------------------------
# Fatal errors - should roll back the transaction
# ---------------------------------------------------------------------------


class FatalRollbackError(AppError):
    """Fatal errors that should trigger a transaction rollback."""

    code = "fatal_error"
    status_code = 500


class PipelineFailedError(FatalRollbackError):
    """Pipeline stage failed fatally."""

    code = "pipeline_failed"

    def __init__(
        self,
        stage: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.stage = stage


# ---------------------------------------------------------------------------
# LLM-specific errors
# ---------------------------------------------------------------------------


class LLMError(AppError):
    """Base class for LLM-related errors."""

    code = "llm_error"


class LLMTimeoutError(LLMError, TimeoutError):
    """LLM call timed out."""

    code = "llm_timeout"


class LLMRateLimitError(LLMError, RateLimitError):
    """LLM provider rate limited us."""

    code = "llm_rate_limited"


class LLMValidationError(LLMError, ValidationError):
    """LLM response failed validation."""

    code = "llm_validation_error"
