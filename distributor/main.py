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
from fastapi.responses import HTMLResponse, PlainTextResponse

from .artifacts import issue_title, to_issue_markdown
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


@app.get("/tasks/{task_id}/issue.md", response_class=PlainTextResponse)
def task_issue_md(task_id: str) -> PlainTextResponse:
    """Return the task result as GitHub-issue-ready markdown."""
    rec = store.get(task_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown task_id")
    if rec.result is None:
        raise HTTPException(status_code=409, detail="task has no result yet")
    body = to_issue_markdown(rec)
    title = issue_title(rec)
    headers = {
        "X-Spare-Change-Issue-Title": title,
        "Content-Disposition": f'inline; filename="{task_id}-issue.md"',
    }
    return PlainTextResponse(content=body, media_type="text/markdown", headers=headers)


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
        output = rec.result.output if rec.result else ""
        recent.append({
            "task_id": rec.task.task_id,
            "project": rec.task.project_slug,
            "path": rec.task.metadata.get("path"),
            "kind": rec.task.metadata.get("kind") or rec.task.kind,
            "status": rec.status.value,
            "result_status": rec.result.status.value if rec.result else None,
            "donor": rec.result.agent_id if rec.result else None,
            "cost_usd": float(rec.result.estimated_cost_usd or 0.0) if rec.result else None,
            "output_chars": len(output),
            "output_preview": output[:600] if output else "",
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
  .impact-byline { padding: 28px 24px; border-bottom: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 32px; flex-wrap: wrap;
    font: 17px/1.5 Charter, "Source Serif Pro", Georgia, "Times New Roman", serif;
    color: var(--text); letter-spacing: -0.005em; }
  .impact-byline .impact-num { font-weight: 600; padding: 0 2px;
    font-variant-numeric: tabular-nums lining-nums;
    font-feature-settings: "lnum" 1, "tnum" 1; }
  .impact-byline .impact-meta { font: 500 10px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    color: var(--muted); text-transform: uppercase; letter-spacing: 0.12em;
    white-space: nowrap; align-self: center; }
  .impact-byline .impact-meta .dot { color: var(--line); margin: 0 6px; }
  .sparkline-strip { padding: 10px 24px; border-bottom: 1px solid var(--line);
    display: flex; align-items: center; gap: 16px; }
  .sparkline-strip svg { flex: 1; height: 32px; display: block; }
  .sparkline-strip .spark-label { font: 500 10px/1 -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    color: var(--muted); text-transform: uppercase; letter-spacing: 0.12em; white-space: nowrap; }
  .sparkline-strip .spark-current { color: var(--green); font-weight: 600;
    font-variant-numeric: tabular-nums; font-size: 12px; padding-left: 4px;
    transition: opacity 0.2s; }
  .sparkline-strip .spark-current.tick { opacity: 0.65; }
  tr.task-row { cursor: pointer; }
  tr.task-row:hover { background: #161e29; }
  tr.preview-row td { padding: 0; border-bottom: 1px solid var(--line); }
  tr.preview-row.hidden { display: none; }
  pre.preview { margin: 0; padding: 12px 14px; background: #07090d; color: #c9d1d9;
    font: 12px/1.55 ui-monospace, "SF Mono", Menlo, monospace; max-height: 360px;
    overflow: auto; white-space: pre-wrap; word-break: break-word; }
  .row-path { color: var(--muted); font-size: 11px; }
  .expander { display: inline-block; width: 12px; color: var(--muted); transition: transform 0.15s; }
  tr.task-row.expanded .expander { transform: rotate(90deg); }
  footer { padding: 16px 24px; color: var(--muted); font-size: 12px; text-align: center; border-top: 1px solid var(--line); margin-top: 24px; }
</style>
</head>
<body>
<header>
  <h1>spare-change <span class="tag">distributor / donor-side dashboard</span></h1>
  <span class="live" id="live">live · refresh 2s</span>
</header>

<div class="impact-byline">
  <span>
    <span class="impact-num" id="impact-bugs">0</span> bugs surfaced in
    <span class="impact-num" id="impact-minutes">0</span> minutes of donated compute,
    across <span class="impact-num" id="impact-projects">0</span> open-source project<span id="proj-plural">s</span>.
  </span>
  <span class="impact-meta">
    <span id="impact-donors">0</span> active donor<span id="donor-plural">s</span>
    <span class="dot">·</span> live, refresh every 2s
  </span>
</div>

<div class="sparkline-strip">
  <svg id="sparkline" viewBox="0 0 600 32" preserveAspectRatio="none" aria-label="donation trend over last 60 seconds">
    <defs>
      <linearGradient id="spark-fill" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="#3fb950" stop-opacity="0.28"/>
        <stop offset="1" stop-color="#3fb950" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path id="spark-area" fill="url(#spark-fill)" d=""/>
    <path id="spark-line" fill="none" stroke="#3fb950" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" d=""/>
  </svg>
  <span class="spark-label">last 60s · cumulative <span class="spark-current" id="spark-current">$0.0000</span></span>
</div>

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
const escapeHtml = (s) => (s || "").replace(/[&<>"']/g, (c) =>
  ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const expanded = new Set();

const SPARK_MAX_POINTS = 30; // 60s at 2s polling
const sparkHistory = [];
let lastSparkUsd = null;

function updateSparkline(totalUsd) {
  const usd = totalUsd || 0;
  sparkHistory.push({ t: Date.now(), usd });
  while (sparkHistory.length > SPARK_MAX_POINTS) sparkHistory.shift();

  const currentEl = document.getElementById("spark-current");
  currentEl.textContent = "$" + usd.toFixed(4);
  if (lastSparkUsd !== null && usd > lastSparkUsd + 1e-9) {
    currentEl.classList.add("tick");
    setTimeout(() => currentEl.classList.remove("tick"), 220);
  }
  lastSparkUsd = usd;

  if (sparkHistory.length < 2) {
    document.getElementById("spark-line").setAttribute("d", "");
    document.getElementById("spark-area").setAttribute("d", "");
    return;
  }
  const usdMin = Math.min(...sparkHistory.map(p => p.usd));
  const usdMax = Math.max(...sparkHistory.map(p => p.usd));
  const range = (usdMax - usdMin) || 0.0001;
  const w = 600, h = 32, padX = 2, padY = 3;

  const pts = sparkHistory.map((p, i) => {
    const x = padX + (i / (SPARK_MAX_POINTS - 1)) * (w - 2 * padX);
    const y = h - padY - ((p.usd - usdMin) / range) * (h - 2 * padY);
    return [x, y];
  });
  const line = pts.map((pt, i) => (i === 0 ? `M${pt[0].toFixed(2)},${pt[1].toFixed(2)}`
                                            : `L${pt[0].toFixed(2)},${pt[1].toFixed(2)}`)).join("");
  const area = line + `L${pts[pts.length-1][0].toFixed(2)},${h} L${pts[0][0].toFixed(2)},${h} Z`;
  document.getElementById("spark-line").setAttribute("d", line);
  document.getElementById("spark-area").setAttribute("d", area);
}

function togglePreview(i) {
  const row = document.querySelector(`tr.task-row[data-idx="${i}"]`);
  const preview = document.querySelector(`tr.preview-row[data-preview="${i}"]`);
  if (!preview) return;
  if (preview.classList.contains("hidden")) {
    preview.classList.remove("hidden");
    row.classList.add("expanded");
    expanded.add(i);
  } else {
    preview.classList.add("hidden");
    row.classList.remove("expanded");
    expanded.delete(i);
  }
}

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
    document.getElementById("impact-bugs").textContent = d.total_bugs_found || 0;
    document.getElementById("impact-minutes").textContent = ((d.total_compute_seconds || 0) / 60).toFixed(1);
    document.getElementById("impact-projects").textContent = d.projects_helped || 0;
    document.getElementById("impact-donors").textContent = d.donors_active || 0;
    document.getElementById("proj-plural").textContent = (d.projects_helped === 1) ? "" : "s";
    document.getElementById("donor-plural").textContent = (d.donors_active === 1) ? "" : "s";
    updateSparkline(d.total_donated_usd);

    const tb = document.getElementById("tasks-body");
    if (!d.recent || d.recent.length === 0) {
      tb.innerHTML = '<tr><td colspan="6" class="empty">No tasks yet — seed one with <code>./scripts/seed_from_repo.sh ...</code></td></tr>';
    } else {
      tb.innerHTML = d.recent.map((t, i) => `
        <tr class="task-row" data-idx="${i}" onclick="togglePreview(${i})">
          <td><span class="expander">▸</span> <code>${t.task_id}</code></td>
          <td>${t.project}${t.path ? `<div class="row-path">${t.path}</div>` : ""}</td>
          <td><span class="pill">${t.kind || "prompt"}</span></td>
          <td>${t.donor || "—"}</td>
          <td>${pill(t.result_status || t.status)}</td>
          <td class="usd">${t.cost_usd ? usd(t.cost_usd) : "—"}</td>
        </tr>
        <tr class="preview-row hidden" data-preview="${i}">
          <td colspan="6"><pre class="preview">${escapeHtml(t.output_preview) || "(no output yet)"}${t.output_chars > 600 ? `\n\n[… truncated, full output is ${t.output_chars.toLocaleString()} chars — fetch via /tasks/${t.task_id}]` : ""}</pre></td>
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


_RECEIPT_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>spare-change — receipt — {donor_id}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg: #0b0f14;
    --panel: #111821;
    --line: #1f2a36;
    --text: #e6edf3;
    --muted: #8b98a5;
    --green: #3fb950;
    --green-dim: #1a4d22;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif; }}
  header {{ padding: 20px 24px; border-bottom: 1px solid var(--line); }}
  header h1 {{ margin: 0; font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }}
  header .sub {{ margin-top: 4px; color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }}
  main {{ padding: 24px; max-width: 1100px; margin: 0 auto; display: grid; gap: 20px; }}
  .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }}
  .panel h2 {{ margin: 0 0 12px 0; font-size: 12px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.06em; }}
  .summary {{ display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 16px; align-items: end; }}
  .summary .label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
  .summary .val {{ font-variant-numeric: tabular-nums; margin-top: 4px; }}
  .summary .val.big {{ font-size: 32px; font-weight: 600; color: var(--green); }}
  .summary .val.med {{ font-size: 20px; font-weight: 600; }}
  .copy {{ color: var(--text); font-size: 13px; line-height: 1.6; }}
  .copy strong {{ color: var(--green); }}
  table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
  th {{ text-align: left; font-size: 11px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.06em; padding: 6px 8px; border-bottom: 1px solid var(--line); font-weight: 600; }}
  td {{ padding: 8px; border-bottom: 1px solid var(--line); font-size: 13px; }}
  tr:last-child td {{ border-bottom: none; }}
  td.usd {{ color: var(--green); text-align: right; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500;
    background: var(--green-dim); color: var(--green); }}
  code {{ font: 12px/1 ui-monospace, "SF Mono", Menlo, monospace; color: var(--muted); }}
  .row-path {{ color: var(--muted); font-size: 11px; }}
  footer {{ padding: 16px 24px; color: var(--muted); font-size: 12px; text-align: center;
    border-top: 1px solid var(--line); margin-top: 24px; }}
  footer a {{ color: var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>spare-change · donation receipt</h1>
  <div class="sub">donor · <code>{donor_id}</code></div>
</header>
<main>
  <div class="panel">
    <h2>Summary</h2>
    <div class="summary">
      <div><div class="label">Total donated</div><div class="val big">${total_usd}</div></div>
      <div><div class="label">Tasks</div><div class="val med">{tasks_count}</div></div>
      <div><div class="label">Projects</div><div class="val med">{projects_count}</div></div>
      <div><div class="label">Session</div><div class="val med">{session_duration}</div></div>
    </div>
  </div>
  <div class="panel copy">
    <p><strong>For your records.</strong> spare-change donations are made by running tasks against your existing Claude Code subscription. The estimated USD value above is computed at public Anthropic API rates against equivalent token counts — useful as a reference for line-item business expense reporting. For tax purposes, consult your accountant; this is not legal advice.</p>
  </div>
  <div class="panel">
    <h2>Tasks</h2>
    <table>
      <thead><tr><th>Task</th><th>Project</th><th>File</th><th>Kind</th><th>Status</th><th style="text-align:right">Cost</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</main>
<footer>generated {generated_at} · <a href="/">← back to dashboard</a></footer>
</body>
</html>
"""


_RECEIPT_EMPTY_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>spare-change — no receipt — {donor_id}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body {{ margin: 0; padding: 0; background: #0b0f14; color: #e6edf3;
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 600px; margin: 80px auto; padding: 32px; background: #111821;
    border: 1px solid #1f2a36; border-radius: 8px; text-align: center; }}
  h1 {{ margin: 0 0 8px 0; font-size: 20px; }}
  p {{ color: #8b98a5; }}
  code {{ font: 12px/1 ui-monospace, "SF Mono", Menlo, monospace; color: #e6edf3; }}
  a {{ color: #3fb950; text-decoration: none; }}
</style>
</head>
<body>
<main>
  <h1>No donations yet</h1>
  <p>No donations yet for donor <code>{donor_id}</code>. Start the agent and seed a task.</p>
  <p><a href="/">← back to dashboard</a></p>
</main>
</body>
</html>
"""


def _collect_receipt_records(donor_id: str) -> list[TaskRecord]:
    out: list[TaskRecord] = []
    for rec in store.list_all():
        if rec.result is None:
            continue
        if rec.result.agent_id != donor_id:
            continue
        if rec.result.status.value != "success":
            continue
        out.append(rec)
    out.sort(
        key=lambda r: (r.result.finished_at if r.result and r.result.finished_at else r.task.created_at),
        reverse=True,
    )
    return out


def _build_receipt_payload(donor_id: str, records: list[TaskRecord]) -> dict:
    tasks: list[dict] = []
    projects: list[str] = []
    total = 0.0
    earliest_started = None
    latest_finished = None
    for rec in records:
        result = rec.result
        cost = float(result.estimated_cost_usd or 0.0) if result else 0.0
        total += cost
        if rec.task.project_slug not in projects:
            projects.append(rec.task.project_slug)
        created = rec.task.created_at
        if created is not None:
            if earliest_started is None or created < earliest_started:
                earliest_started = created
        finished = result.finished_at if result else None
        if finished is not None:
            if latest_finished is None or finished > latest_finished:
                latest_finished = finished
        tasks.append({
            "task_id": rec.task.task_id,
            "project": rec.task.project_slug,
            "path": rec.task.metadata.get("path"),
            "kind": rec.task.metadata.get("kind") or rec.task.kind,
            "status": result.status.value if result else rec.status.value,
            "cost_usd": cost,
            "finished_at": finished.isoformat() if finished else None,
            "output_chars": len(result.output or "") if result else 0,
        })
    return {
        "donor_id": donor_id,
        "tasks_completed": len(records),
        "total_donated_usd": total,
        "projects_helped": projects,
        "tasks": tasks,
        "session_started_at": earliest_started.isoformat() if earliest_started else None,
        "session_ended_at": latest_finished.isoformat() if latest_finished else None,
    }


def _format_session_duration(started_iso: str | None, ended_iso: str | None) -> str:
    if not started_iso or not ended_iso:
        return "—"
    try:
        from datetime import datetime as _dt
        start = _dt.fromisoformat(started_iso)
        end = _dt.fromisoformat(ended_iso)
    except ValueError:
        return "—"
    delta = end - start
    secs = int(delta.total_seconds())
    if secs < 0:
        return "—"
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    return f"{hours}h {minutes}m"


def _escape_receipt_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


@app.get("/api/receipts/{donor_id}")
def api_receipt(donor_id: str) -> dict:
    records = _collect_receipt_records(donor_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"no completed donations for donor {donor_id}")
    return _build_receipt_payload(donor_id, records)


@app.get("/receipts/{donor_id}", response_class=HTMLResponse)
def receipt_page(donor_id: str) -> HTMLResponse:
    from datetime import datetime as _dt, timezone as _tz
    records = _collect_receipt_records(donor_id)
    if not records:
        html = _RECEIPT_EMPTY_HTML.format(donor_id=_escape_receipt_html(donor_id))
        return HTMLResponse(content=html, status_code=404)
    payload = _build_receipt_payload(donor_id, records)
    rows_html_parts: list[str] = []
    for t in payload["tasks"]:
        path_cell = _escape_receipt_html(t["path"]) if t.get("path") else "—"
        rows_html_parts.append(
            "<tr>"
            f'<td><code>{_escape_receipt_html(t["task_id"])}</code></td>'
            f'<td>{_escape_receipt_html(t["project"])}</td>'
            f'<td>{path_cell}</td>'
            f'<td><span class="pill">{_escape_receipt_html(t["kind"] or "prompt")}</span></td>'
            f'<td><span class="pill">{_escape_receipt_html(t["status"])}</span></td>'
            f'<td class="usd">${t["cost_usd"]:.4f}</td>'
            "</tr>"
        )
    rows_html = "".join(rows_html_parts) or '<tr><td colspan="6">—</td></tr>'
    duration = _format_session_duration(
        payload["session_started_at"], payload["session_ended_at"]
    )
    generated_at = _dt.now(_tz.utc).isoformat(timespec="seconds")
    html = _RECEIPT_HTML_TEMPLATE.format(
        donor_id=_escape_receipt_html(donor_id),
        total_usd=f'{payload["total_donated_usd"]:.4f}',
        tasks_count=payload["tasks_completed"],
        projects_count=len(payload["projects_helped"]),
        session_duration=duration,
        rows=rows_html,
        generated_at=generated_at,
    )
    return HTMLResponse(content=html)


_DISCOVER_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>spare-change — find projects</title>
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
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif; }
  header { padding: 20px 24px; border-bottom: 1px solid var(--line);
    display: flex; justify-content: space-between; align-items: baseline; }
  header h1 { margin: 0; font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }
  header h1 span.tag { color: var(--muted); font-weight: 400; margin-left: 8px; font-size: 13px; }
  header a.back { color: var(--muted); font-size: 12px; text-decoration: none; }
  header a.back:hover { color: var(--text); }
  main { padding: 32px 24px 48px; max-width: 920px; margin: 0 auto; }
  .intro { color: var(--muted); font-size: 14px; line-height: 1.6; max-width: 640px;
    margin: 0 0 32px 0; }
  .intro strong { color: var(--text); font-weight: 500; }
  .intro code { font: 12px/1 ui-monospace, "SF Mono", Menlo, monospace; color: var(--text); }
  .project { padding: 28px 0; border-top: 1px solid var(--line); }
  .project:last-child { border-bottom: 1px solid var(--line); }
  .project .top { display: flex; justify-content: space-between; align-items: flex-start;
    gap: 24px; flex-wrap: wrap; }
  .project .left { flex: 1 1 380px; min-width: 0; }
  .project .right { flex: 0 0 auto; text-align: right; font-variant-numeric: tabular-nums; }
  .project h3 { margin: 0; font-size: 17px; font-weight: 600; letter-spacing: -0.005em; }
  .project h3 a { color: var(--text); text-decoration: none; }
  .project h3 a:hover { color: var(--green); }
  .project .slug { font: 12px/1.4 ui-monospace, "SF Mono", Menlo, monospace;
    color: var(--muted); margin-top: 4px; }
  .project .blurb { margin: 10px 0 12px 0; color: var(--text); font-size: 14px;
    line-height: 1.55; max-width: 560px; }
  .accepts { margin: 8px 0 0 0; }
  .accepts .pill { display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 500; background: var(--green-dim); color: var(--green);
    margin-right: 6px; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .stats-row { display: flex; gap: 22px; align-items: baseline; justify-content: flex-end;
    flex-wrap: wrap; }
  .stats-row .stat { text-align: right; }
  .stats-row .stat .label { font-size: 10px; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.08em; }
  .stats-row .stat .val { font-size: 18px; font-weight: 600; margin-top: 2px;
    font-variant-numeric: tabular-nums; }
  .stats-row .stat .val.usd { color: var(--green); }
  .ext { display: inline-block; margin-top: 10px; color: var(--muted); font-size: 12px;
    text-decoration: none; }
  .ext:hover { color: var(--text); }
  .snippet { margin-top: 16px; background: #07090d; border: 1px solid var(--line);
    border-radius: 6px; padding: 12px 14px; position: relative; max-width: 560px; }
  .snippet pre { margin: 0; font: 12px/1.55 ui-monospace, "SF Mono", Menlo, monospace;
    color: #c9d1d9; white-space: pre; overflow-x: auto; padding-right: 80px; }
  .snippet .copy-btn { position: absolute; top: 8px; right: 8px; background: transparent;
    border: 1px solid var(--line); color: var(--muted); font-size: 11px; padding: 3px 8px;
    border-radius: 4px; cursor: pointer; font-family: inherit; }
  .snippet .copy-btn:hover { color: var(--text); border-color: var(--muted); }
  .snippet .copied { position: absolute; top: 8px; right: 8px; font-size: 11px;
    color: var(--green); padding: 4px 8px; opacity: 0; transition: opacity 0.2s;
    pointer-events: none; background: #07090d; }
  .snippet .copied.show { opacity: 1; }
  .empty { color: var(--muted); padding: 48px 0; text-align: center; font-size: 14px; }
  footer { padding: 16px 24px; color: var(--muted); font-size: 12px; text-align: center;
    border-top: 1px solid var(--line); margin-top: 24px; }
  footer a { color: var(--muted); }
</style>
</head>
<body>
<header>
  <h1>spare-change <span class="tag">· find projects</span></h1>
  <a class="back" href="/">back to dashboard →</a>
</header>

<main>
  <p class="intro">
    These open-source projects are <strong>accepting donor compute</strong> via spare-change.
    Copy a project's config snippet to add it to your donor allowlist — once it's in
    <code>config.yaml</code>, your idle Claude Code subscription can pick up its tasks.
  </p>
  <div id="projects"><div class="empty">Loading…</div></div>
</main>
<footer>spare-change · <a href="/">dashboard</a></footer>

<script>
const escapeHtml = (s) => (s == null ? "" : String(s)).replace(/[&<>"']/g, (c) =>
  ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const usd = (n) => "$" + (n || 0).toFixed(4);

function copySnippet(idx, slug) {
  const text = "project_allowlist:\\n  - " + slug;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      const flag = document.getElementById("copied-" + idx);
      if (!flag) return;
      flag.classList.add("show");
      setTimeout(() => flag.classList.remove("show"), 1500);
    }).catch(() => {});
  }
}

async function load() {
  const host = document.getElementById("projects");
  try {
    const r = await fetch("/api/discover");
    const d = await r.json();
    const projects = d.projects || [];
    if (projects.length === 0) {
      host.innerHTML = '<div class="empty">No projects registered yet.</div>';
      return;
    }
    host.innerHTML = projects.map((p, i) => {
      const accepts = (p.accepts || []).map((k) =>
        `<span class="pill">${escapeHtml(k)}</span>`).join("");
      const stats = p.stats || {};
      const snippetText = "project_allowlist:\\n  - " + p.slug;
      return `
        <div class="project">
          <div class="top">
            <div class="left">
              <h3><a href="${escapeHtml(p.url)}" target="_blank" rel="noopener">${escapeHtml(p.name)}</a></h3>
              <div class="slug">${escapeHtml(p.slug)}</div>
              <p class="blurb">${escapeHtml(p.blurb)}</p>
              <div class="accepts">${accepts}</div>
              <a class="ext" href="${escapeHtml(p.url)}" target="_blank" rel="noopener">github ↗</a>
            </div>
            <div class="right">
              <div class="stats-row">
                <div class="stat"><div class="label">Tasks</div><div class="val">${stats.tasks || 0}</div></div>
                <div class="stat"><div class="label">Donated</div><div class="val usd">${usd(stats.usd)}</div></div>
                <div class="stat"><div class="label">Bugs</div><div class="val">${stats.bugs_found || 0}</div></div>
                <div class="stat"><div class="label">Donors</div><div class="val">${stats.donors || 0}</div></div>
              </div>
            </div>
          </div>
          <div class="snippet">
            <pre>${escapeHtml(snippetText)}</pre>
            <button class="copy-btn" onclick="copySnippet(${i}, '${escapeHtml(p.slug)}')">Copy snippet</button>
            <span class="copied" id="copied-${i}">Copied!</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    host.innerHTML = '<div class="empty">Could not load projects.</div>';
  }
}

load();
</script>
</body>
</html>
"""


@app.get("/api/discover")
def api_discover() -> dict:
    from pathlib import Path as _Path
    import json as _json

    path = _Path(__file__).resolve().parent.parent / "data" / "registered_projects.json"
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = _json.load(fh)
        raw_projects = data.get("projects", []) or []
    except FileNotFoundError:
        log.warning("registered_projects.json not found at %s", path)
        return {"projects": []}
    except (OSError, ValueError) as exc:
        log.warning("could not read registered_projects.json: %s", exc)
        return {"projects": []}

    agg = store.aggregate()
    by_project = (agg.get("by_project") or {}) if isinstance(agg, dict) else {}

    donors_by_project: dict[str, set[str]] = {}
    for rec in store.list_all():
        if rec.result is None:
            continue
        status_val = getattr(getattr(rec.result, "status", None), "value", None)
        if status_val != "success":
            continue
        slug = rec.task.project_slug
        donors_by_project.setdefault(slug, set()).add(rec.result.agent_id)

    enriched: list[dict] = []
    for entry in raw_projects:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        proj_stats = by_project.get(slug) if slug else None
        stats = {
            "tasks": int(proj_stats.get("tasks", 0)) if proj_stats else 0,
            "usd": float(proj_stats.get("usd", 0.0)) if proj_stats else 0.0,
            "bugs_found": int(proj_stats.get("bugs_found", 0)) if proj_stats else 0,
            "donors": len(donors_by_project.get(slug, set())) if slug else 0,
        }
        enriched.append({**entry, "stats": stats})

    return {"projects": enriched}


@app.get("/discover", response_class=HTMLResponse)
def discover_page() -> HTMLResponse:
    return HTMLResponse(content=_DISCOVER_HTML)


def main() -> None:
    uvicorn.run("distributor.main:app", host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()
