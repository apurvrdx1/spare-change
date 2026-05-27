"""Agent-side wire schemas.

Imports from `distributor.schemas` to keep the wire contract in one place.
If we ever split the distributor into its own repo, this file becomes the
duplicate-or-vendor seam.
"""
from distributor.schemas import (
    ContextFile,
    ResultStatus,
    Task,
    WebhookResult,
)

__all__ = ["ContextFile", "ResultStatus", "Task", "WebhookResult"]
