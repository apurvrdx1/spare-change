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

    def aggregate(self) -> dict:
        """Roll up queue counts and per-donor / per-project donation totals."""
        with self._lock:
            records = list(self._records.values())

        queue = {"pending": 0, "in_flight": 0, "done": 0, "failed": 0}
        by_donor: dict[str, dict] = {}
        by_project: dict[str, dict] = {}
        total_usd = 0.0
        total_tasks_done = 0

        for rec in records:
            queue_key = rec.status.value if rec.status.value in queue else None
            if queue_key:
                queue[queue_key] += 1

            if rec.result is None:
                continue

            cost = float(rec.result.estimated_cost_usd or 0.0)
            donor = rec.result.agent_id
            project = rec.task.project_slug

            d = by_donor.setdefault(donor, {"tasks": 0, "usd": 0.0})
            d["tasks"] += 1
            d["usd"] += cost

            p = by_project.setdefault(project, {"tasks": 0, "usd": 0.0})
            p["tasks"] += 1
            p["usd"] += cost

            total_usd += cost
            if rec.result.status == ResultStatus.SUCCESS:
                total_tasks_done += 1

        return {
            "queue": queue,
            "total_donated_usd": total_usd,
            "total_tasks_done": total_tasks_done,
            "by_donor": by_donor,
            "by_project": by_project,
        }
