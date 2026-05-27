from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class CreditWindow(BaseModel):
    weekly_reset_day: str = "monday"
    weekly_reset_hour: int = 9
    donate_last_hours: int = 10
    bypass: bool = False


class AgentConfig(BaseModel):
    agent_id: str = "agent_anonymous"
    distributor_url: str = "http://127.0.0.1:8080"
    auth_token: Optional[str] = None
    poll_interval_seconds: int = 5
    credit_window: CreditWindow
    project_allowlist: list[str] = Field(default_factory=list)
    enforce_allowlist: bool = False
    max_cost_per_task_usd: float = 0.50
    claude_cli_path: str = "claude"
    claude_extra_args: list[str] = Field(default_factory=lambda: ["--print"])


def load_config(path: str | Path) -> AgentConfig:
    """Read YAML, validate, return AgentConfig. Raise on parse/validation error."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AgentConfig.model_validate(data)
