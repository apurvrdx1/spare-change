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
import os
import secrets
import uuid
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

from .schemas import CreateTaskRequest, Task, TaskRecord, WebhookResult
from .store import TaskStore


def _expected_token() -> str:
    return os.environ.get("SPARE_CHANGE_DISTRIBUTOR_TOKEN", "").strip()


def require_auth(authorization: str | None = Header(default=None)) -> None:
    expected = _expected_token()
    if not expected:
        return None
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    provided = authorization[len("Bearer "):]
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="invalid token")
    return None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [distributor] %(message)s",
)
log = logging.getLogger("distributor")

app = FastAPI(title="spare-change distributor", version="0.1.0")
store = TaskStore()


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/tasks", response_model=Task, dependencies=[Depends(require_auth)])
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


@app.get("/tasks/next", response_model=Optional[Task], dependencies=[Depends(require_auth)])
def next_task() -> Optional[Task]:
    task = store.claim_next()
    if task is None:
        return None
    log.info("claimed task_id=%s project=%s", task.task_id, task.project_slug)
    return task


@app.post("/webhook/{task_id}", dependencies=[Depends(require_auth)])
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


@app.get("/api/dashboard")
def api_dashboard() -> dict:
    agg = store.aggregate()
    records = sorted(
        store.list_all(),
        key=lambda r: (r.result.finished_at if r.result and r.result.finished_at else r.task.created_at),
        reverse=True,
    )[:12]
    recent = []
    for rec in records:
        recent.append({
            "task_id": rec.task.task_id,
            "project": rec.task.project_slug,
            "kind": rec.task.metadata.get("kind") or rec.task.kind,
            "status": rec.status.value,
            "result_status": rec.result.status.value if rec.result else None,
            "donor": rec.result.agent_id if rec.result else None,
            "cost_usd": float(rec.result.estimated_cost_usd or 0.0) if rec.result else None,
            "output_chars": len(rec.result.output) if rec.result else 0,
            "created_at": rec.task.created_at.isoformat() if rec.task.created_at else None,
            "finished_at": rec.result.finished_at.isoformat() if rec.result and rec.result.finished_at else None,
        })
    agg["recent"] = recent
    return agg


_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>spare-change — distributor</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    --bg: #0b0f14;
    --panel: #111821;
    --line: #1f2a36;
    --text: #e6edf3;
    --muted: #8b98a5;
    --green: #3fb950;
    --green-dim: #1a4d22;
    --amber: #d29922;
    --blue: #58a6ff;
    --red: #f85149;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif; }
  header { padding: 20px 24px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: baseline; }
  header h1 { margin: 0; font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }
  header h1 span.tag { color: var(--muted); font-weight: 400; margin-left: 8px; font-size: 13px; }
  header .live { font-size: 12px; color: var(--green); }
  header .live::before { content: "● "; }
  main { padding: 24px; display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px; max-width: 1400px; margin: 0 auto; }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }
  .panel h2 { margin: 0 0 12px 0; font-size: 12px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.06em; }
  .stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; grid-column: 1 / -1; }
  .stat { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
  .stat .label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
  .stat .val { font-size: 22px; font-weight: 600; margin-top: 4px; font-variant-numeric: tabular-nums; }
  .stat .val.donated { color: var(--green); }
  .stat .val.pending { color: var(--amber); }
  .stat .val.in_flight { color: var(--blue); }
  .stat .val.failed { color: var(--red); }
  table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th { text-align: left; font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.06em; padding: 6px 8px; border-bottom: 1px solid var(--line); font-weight: 600; }
  td { padding: 8px; border-bottom: 1px solid var(--line); font-size: 13px; }
  tr:last-child td { border-bottom: none; }
  td.usd { color: var(--green); text-align: right; }
  td.num { text-align: right; color: var(--muted); }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
  .pill.success { background: var(--green-dim); color: var(--green); }
  .pill.pending { background: #4a3a10; color: var(--amber); }
  .pill.in_flight { background: #0b3a66; color: var(--blue); }
  .pill.done { background: var(--green-dim); color: var(--green); }
  .pill.failed { background: #4a1414; color: var(--red); }
  code { font: 12px/1 ui-monospace, "SF Mono", Menlo, monospace; color: var(--muted); }
  .empty { color: var(--muted); font-size: 13px; padding: 12px 0; text-align: center; }
  footer { padding: 16px 24px; color: var(--muted); font-size: 12px; text-align: center; border-top: 1px solid var(--line); margin-top: 24px; }
</style>
</head>
<body>
<header>
  <h1>spare-change <span class="tag">distributor / donor-side dashboard</span></h1>
  <span class="live" id="live">live · refresh 2s</span>
</header>
<main>
  <div class="stats">
    <div class="stat"><div class="label">Donated</div><div class="val donated" id="donated">$0.00</div></div>
    <div class="stat"><div class="label">Pending</div><div class="val pending" id="pending">0</div></div>
    <div class="stat"><div class="label">In flight</div><div class="val in_flight" id="in_flight">0</div></div>
    <div class="stat"><div class="label">Done</div><div class="val" id="done">0</div></div>
    <div class="stat"><div class="label">Failed</div><div class="val failed" id="failed">0</div></div>
  </div>

  <div class="panel">
    <h2>Recent tasks</h2>
    <table id="tasks-table">
      <thead><tr>
        <th>Task</th><th>Project</th><th>Kind</th><th>Donor</th>
        <th>Status</th><th style="text-align:right">Cost</th>
      </tr></thead>
      <tbody id="tasks-body"><tr><td colspan="6" class="empty">No tasks yet — seed one with <code>./scripts/seed_from_repo.sh ...</code></td></tr></tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Donors</h2>
    <table id="donors-table">
      <thead><tr><th>Donor</th><th class="num">Tasks</th><th class="num">Contributed</th></tr></thead>
      <tbody id="donors-body"><tr><td colspan="3" class="empty">No donations yet</td></tr></tbody>
    </table>
    <h2 style="margin-top: 20px;">Projects</h2>
    <table id="projects-table">
      <thead><tr><th>Project</th><th class="num">Tasks</th><th class="num">Received</th></tr></thead>
      <tbody id="projects-body"><tr><td colspan="3" class="empty">No donations yet</td></tr></tbody>
    </table>
  </div>
</main>
<footer>spare-change · in-memory queue · <code>./scripts/seed_from_repo.sh OWNER/REPO PATH [annotate|review|test-gen]</code></footer>

<script>
const fmt = (n) => "$" + (n || 0).toFixed(4);
const usd = (n) => "$" + (n || 0).toFixed(4);
const STATUS_LABEL = { success: "success", failed: "failed", timeout: "timeout",
  skipped_outside_window: "skipped (window)", skipped_not_allowlisted: "skipped (allowlist)" };

function pill(status) {
  const cls = ["success","done","in_flight","pending","failed","timeout"].includes(status) ? status : "pending";
  return `<span class="pill ${cls === "timeout" ? "failed" : cls}">${STATUS_LABEL[status] || status}</span>`;
}

async function refresh() {
  try {
    const r = await fetch("/api/dashboard");
    const d = await r.json();
    document.getElementById("donated").textContent = usd(d.total_donated_usd);
    document.getElementById("pending").textContent = d.queue.pending;
    document.getElementById("in_flight").textContent = d.queue.in_flight;
    document.getElementById("done").textContent = d.queue.done;
    document.getElementById("failed").textContent = d.queue.failed;

    const tb = document.getElementById("tasks-body");
    if (!d.recent || d.recent.length === 0) {
      tb.innerHTML = '<tr><td colspan="6" class="empty">No tasks yet — seed one with <code>./scripts/seed_from_repo.sh ...</code></td></tr>';
    } else {
      tb.innerHTML = d.recent.map(t => `
        <tr>
          <td><code>${t.task_id}</code></td>
          <td>${t.project}</td>
          <td><span class="pill">${t.kind || "prompt"}</span></td>
          <td>${t.donor || "—"}</td>
          <td>${pill(t.result_status || t.status)}</td>
          <td class="usd">${t.cost_usd ? usd(t.cost_usd) : "—"}</td>
        </tr>
      `).join("");
    }

    const donors = Object.entries(d.by_donor || {}).sort((a,b) => b[1].usd - a[1].usd);
    const db = document.getElementById("donors-body");
    if (donors.length === 0) {
      db.innerHTML = '<tr><td colspan="3" class="empty">No donations yet</td></tr>';
    } else {
      db.innerHTML = donors.map(([name, s]) => `
        <tr><td>${name}</td><td class="num">${s.tasks}</td><td class="usd">${usd(s.usd)}</td></tr>
      `).join("");
    }

    const projects = Object.entries(d.by_project || {}).sort((a,b) => b[1].usd - a[1].usd);
    const pb = document.getElementById("projects-body");
    if (projects.length === 0) {
      pb.innerHTML = '<tr><td colspan="3" class="empty">No donations yet</td></tr>';
    } else {
      pb.innerHTML = projects.map(([name, s]) => `
        <tr><td>${name}</td><td class="num">${s.tasks}</td><td class="usd">${usd(s.usd)}</td></tr>
      `).join("");
    }
  } catch (e) {
    document.getElementById("live").textContent = "offline";
    document.getElementById("live").style.color = "var(--red)";
  }
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_DASHBOARD_HTML)


def main() -> None:
    uvicorn.run("distributor.main:app", host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()
