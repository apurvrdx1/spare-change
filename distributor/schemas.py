from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    DONE = "done"
    FAILED = "failed"


class ResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED_OUTSIDE_WINDOW = "skipped_outside_window"
    SKIPPED_NOT_ALLOWLISTED = "skipped_not_allowlisted"


class ContextFile(BaseModel):
    path: str
    content: str


class Task(BaseModel):
    task_id: str
    project_slug: str
    kind: str = "prompt"
    prompt: str
    context_files: list[ContextFile] = Field(default_factory=list)
    max_cost_usd: float = 0.50
    timeout_seconds: int = 120
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    callback_url: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class CreateTaskRequest(BaseModel):
    project_slug: str
    prompt: str
    context_files: list[ContextFile] = Field(default_factory=list)
    max_cost_usd: float = 0.50
    timeout_seconds: int = 120
    metadata: dict = Field(default_factory=dict)


class WebhookResult(BaseModel):
    task_id: str
    agent_id: str
    status: ResultStatus
    output: str = ""
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


class TaskRecord(BaseModel):
    task: Task
    status: TaskStatus
    result: Optional[WebhookResult] = None
