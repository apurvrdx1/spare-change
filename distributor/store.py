"""In-memory task queue + status registry.

Process-local, no persistence. Swap-point: replace with NATS JetStream pull
consumer (or Redis Streams) for multi-host, multi-agent deployment.
"""
from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Optional

from .schemas import ResultStatus, Task, TaskRecord, TaskStatus, WebhookResult


class TaskStore:
    def __init__(self) -> None:
        self._records: dict[str, TaskRecord] = {}
        self._pending: deque[str] = deque()
        self._lock = Lock()

    def add(self, task: Task) -> None:
        with self._lock:
            self._records[task.task_id] = TaskRecord(task=task, status=TaskStatus.PENDING)
            self._pending.append(task.task_id)

    def claim_next(self) -> Optional[Task]:
        with self._lock:
            while self._pending:
                tid = self._pending.popleft()
                rec = self._records.get(tid)
                if rec is not None and rec.status == TaskStatus.PENDING:
                    rec.status = TaskStatus.IN_FLIGHT
                    return rec.task
            return None

    def record_result(self, task_id: str, result: WebhookResult) -> None:
        with self._lock:
            rec = self._records.get(task_id)
            if rec is None:
                raise KeyError(task_id)
            rec.result = result
            rec.status = (
                TaskStatus.DONE
                if result.status == ResultStatus.SUCCESS
                else TaskStatus.FAILED
            )

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._records.get(task_id)

    def list_all(self) -> list[TaskRecord]:
        with self._lock:
            return list(self._records.values())
