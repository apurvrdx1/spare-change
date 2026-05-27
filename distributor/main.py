"""spare-change distributor — FastAPI app.

Endpoints
---------
POST /tasks               -- maintainer seeds a new task
GET  /tasks/next          -- agent claims the next pending task (null if empty)
POST /webhook/{task_id}   -- agent posts the result
GET  /tasks               -- list all task records (debugging / demo view)
GET  /tasks/{task_id}     -- inspect a single task

This is the MVP placeholder for what will become a NATS JetStream gateway.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException

from .schemas import CreateTaskRequest, Task, TaskRecord, WebhookResult
from .store import TaskStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [distributor] %(message)s",
)
log = logging.getLogger("distributor")

app = FastAPI(title="spare-change distributor", version="0.1.0")
store = TaskStore()


@app.post("/tasks", response_model=Task)
def create_task(req: CreateTaskRequest) -> Task:
    task = Task(
        task_id=f"tsk_{uuid.uuid4().hex[:12]}",
        project_slug=req.project_slug,
        prompt=req.prompt,
        context_files=req.context_files,
        max_cost_usd=req.max_cost_usd,
        timeout_seconds=req.timeout_seconds,
        metadata=req.metadata,
    )
    store.add(task)
    log.info("seeded task_id=%s project=%s files=%d", task.task_id, task.project_slug, len(task.context_files))
    return task


@app.get("/tasks/next", response_model=Optional[Task])
def next_task() -> Optional[Task]:
    task = store.claim_next()
    if task is None:
        return None
    log.info("claimed task_id=%s project=%s", task.task_id, task.project_slug)
    return task


@app.post("/webhook/{task_id}")
def webhook(task_id: str, result: WebhookResult) -> dict:
    if result.task_id != task_id:
        raise HTTPException(status_code=400, detail="task_id mismatch")
    try:
        store.record_result(task_id, result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="unknown task_id") from exc
    log.info(
        "result task_id=%s status=%s output_chars=%d",
        task_id, result.status.value, len(result.output or ""),
    )
    log.info(
        "\n----- RESULT %s (%s) -----\n%s\n----- END -----",
        task_id, result.status.value, (result.output or "")[:4000],
    )
    return {"ok": True}


@app.get("/tasks", response_model=list[TaskRecord])
def list_tasks() -> list[TaskRecord]:
    return store.list_all()


@app.get("/tasks/{task_id}", response_model=TaskRecord)
def get_task(task_id: str) -> TaskRecord:
    rec = store.get(task_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown task_id")
    return rec


def main() -> None:
    uvicorn.run("distributor.main:app", host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()
