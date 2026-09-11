"""Schemas for task management and pipeline/agent task results."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Type of task."""

    PIPELINE = "pipeline"
    AGENT = "agent"


class TaskCreate(BaseModel):
    """Request to create a new task."""

    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    task_type: TaskType = Field(default=TaskType.PIPELINE)
    max_steps: Optional[int] = Field(default=None, ge=1, le=20)
    stream: bool = Field(default=False, description="Whether to stream results via SSE")


class TaskResponse(BaseModel):
    """Response when creating or querying a task."""

    task_id: str
    task_type: TaskType
    status: TaskStatus
    query: str
    created_at: datetime
    updated_at: datetime
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    current_stage: Optional[str] = None


class TaskListResponse(BaseModel):
    """Paginated list of tasks."""

    tasks: list[TaskResponse]
    total: int
