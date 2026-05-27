"""spare-change donor agent daemon.

Polls the distributor for tasks, gates on credit window + allowlist, runs
`claude --print` as a subprocess against the donor's existing Claude Code
session, then POSTs the result back to the distributor's webhook.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from types import FrameType
from typing import Optional

import httpx

from .config import AgentConfig, load_config
from .runner import run_claude
from .schemas import ResultStatus, Task, WebhookResult
from .window import is_in_credit_window

log = logging.getLogger("agent")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _in_window(cfg: AgentConfig) -> bool:
    if cfg.credit_window.bypass:
        return True
    return is_in_credit_window(
        _now_utc(),
        cfg.credit_window.weekly_reset_day,
        cfg.credit_window.weekly_reset_hour,
        cfg.credit_window.donate_last_hours,
    )


def _in_allowlist(cfg: AgentConfig, project_slug: str) -> bool:
    if not cfg.enforce_allowlist:
        return True
    return project_slug in cfg.project_allowlist


def _auth_headers(cfg: AgentConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.auth_token}"} if cfg.auth_token else {}


def claim_next(client: httpx.Client, cfg: AgentConfig) -> Optional[Task]:
    url = f"{cfg.distributor_url.rstrip('/')}/tasks/next"
    try:
        r = client.get(url, headers=_auth_headers(cfg), timeout=10.0)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("claim failed: %s", exc)
        return None
    body = r.text.strip()
    if not body or body == "null":
        return None
    return Task.model_validate_json(body)


def post_result(client: httpx.Client, cfg: AgentConfig, result: WebhookResult) -> None:
    url = f"{cfg.distributor_url.rstrip('/')}/webhook/{result.task_id}"
    try:
        r = client.post(
            url,
            content=result.model_dump_json(),
            headers={**_auth_headers(cfg), "Content-Type": "application/json"},
            timeout=10.0,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("webhook POST failed task_id=%s: %s", result.task_id, exc)


def handle_task(cfg: AgentConfig, task: Task) -> WebhookResult:
    if not _in_window(cfg):
        log.info("task %s skipped: outside credit window", task.task_id)
        now = _now_utc()
        return WebhookResult(
            task_id=task.task_id,
            agent_id=cfg.agent_id,
            status=ResultStatus.SKIPPED_OUTSIDE_WINDOW,
            output="",
            started_at=now,
            finished_at=now,
        )
    if not _in_allowlist(cfg, task.project_slug):
        log.info(
            "task %s skipped: project %s not in allowlist",
            task.task_id, task.project_slug,
        )
        now = _now_utc()
        return WebhookResult(
            task_id=task.task_id,
            agent_id=cfg.agent_id,
            status=ResultStatus.SKIPPED_NOT_ALLOWLISTED,
            output="",
            started_at=now,
            finished_at=now,
        )

    log.info("running task=%s project=%s", task.task_id, task.project_slug)
    outcome = run_claude(
        prompt=task.prompt,
        context_files=task.context_files,
        timeout_seconds=task.timeout_seconds,
        cli_path=cfg.claude_cli_path,
        extra_args=cfg.claude_extra_args,
    )
    log.info(
        "completed task=%s status=%s exit=%s output_chars=%d",
        task.task_id, outcome.status.value, outcome.exit_code, len(outcome.output or ""),
    )
    return WebhookResult(
        task_id=task.task_id,
        agent_id=cfg.agent_id,
        status=outcome.status,
        output=outcome.output,
        error=outcome.error,
        started_at=outcome.started_at,
        finished_at=outcome.finished_at,
        exit_code=outcome.exit_code,
        estimated_cost_usd=outcome.estimated_cost_usd,
    )


_running = True


def _shutdown(signum: int, _frame: Optional[FrameType]) -> None:
    global _running
    _running = False
    log.info("shutdown signal received (%s); finishing current loop", signum)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [agent] %(message)s",
    )
    parser = argparse.ArgumentParser(description="spare-change donor agent")
    parser.add_argument("--config", "-c", required=True, help="path to config.yaml")
    parser.add_argument("--once", action="store_true", help="exit after a single iteration")
    args = parser.parse_args()

    cfg = load_config(args.config)
    log.info(
        "agent_id=%s distributor=%s window_bypass=%s allowlist_enforced=%s allowlist_size=%d",
        cfg.agent_id, cfg.distributor_url, cfg.credit_window.bypass,
        cfg.enforce_allowlist, len(cfg.project_allowlist),
    )

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    with httpx.Client() as client:
        while _running:
            try:
                task = claim_next(client, cfg)
                if task is None:
                    if args.once:
                        log.info("no task; --once specified; exiting")
                        return 0
                    time.sleep(cfg.poll_interval_seconds)
                    continue
                result = handle_task(cfg, task)
                post_result(client, cfg, result)
                if args.once:
                    return 0
            except Exception as exc:  # noqa: BLE001
                log.exception("loop error: %s", exc)
                time.sleep(cfg.poll_interval_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
