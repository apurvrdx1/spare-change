"""Wrap a `claude --print` subprocess call with timeout-safe execution."""
import os
import signal
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from agent.schemas import ContextFile, ResultStatus


@dataclass
class RunOutcome:
    status: ResultStatus
    output: str
    error: Optional[str]
    started_at: datetime
    finished_at: datetime
    exit_code: Optional[int]
    input_chars: int = 0
    output_chars: int = 0
    estimated_cost_usd: Optional[float] = None


# Rough public pricing for `claude --print` (assumes Sonnet 4.6 default).
# Override with SPARE_CHANGE_MODEL_INPUT_USD_PER_MTOK / _OUTPUT_USD_PER_MTOK if your default model differs.
_INPUT_USD_PER_MTOK = float(os.environ.get("SPARE_CHANGE_MODEL_INPUT_USD_PER_MTOK", "3.0"))
_OUTPUT_USD_PER_MTOK = float(os.environ.get("SPARE_CHANGE_MODEL_OUTPUT_USD_PER_MTOK", "15.0"))
_CHARS_PER_TOKEN = 4.0


def _estimate_cost_usd(input_chars: int, output_chars: int) -> float:
    input_mtoks = (input_chars / _CHARS_PER_TOKEN) / 1_000_000
    output_mtoks = (output_chars / _CHARS_PER_TOKEN) / 1_000_000
    return input_mtoks * _INPUT_USD_PER_MTOK + output_mtoks * _OUTPUT_USD_PER_MTOK


def _build_full_prompt(prompt: str, context_files: list[ContextFile]) -> str:
    parts = [prompt]
    for file in context_files:
        parts.append("")
        parts.append(f"=== Context: {file.path} ===")
        parts.append(file.content)
        parts.append(f"=== End: {file.path} ===")
    return "\n".join(parts)


def run_claude(
    prompt: str,
    context_files: list[ContextFile],
    timeout_seconds: int,
    cli_path: str = "claude",
    extra_args: Optional[list[str]] = None,
    cwd: Optional[str] = None,
) -> RunOutcome:
    """Run the Claude CLI as a subprocess with hang-proof timeout handling."""
    full_prompt = _build_full_prompt(prompt, context_files)
    input_chars = len(full_prompt)
    args = [cli_path, *(extra_args or [])]
    started_at = datetime.now(timezone.utc)

    try:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        finished_at = datetime.now(timezone.utc)
        return RunOutcome(
            status=ResultStatus.FAILED,
            output="",
            error=f"CLI not found: {exc}",
            started_at=started_at,
            finished_at=finished_at,
            exit_code=None,
        )
    except OSError as exc:
        finished_at = datetime.now(timezone.utc)
        return RunOutcome(
            status=ResultStatus.FAILED,
            output="",
            error=f"Failed to spawn subprocess: {exc}",
            started_at=started_at,
            finished_at=finished_at,
            exit_code=None,
        )

    try:
        stdout, stderr = proc.communicate(input=full_prompt, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        # Kill the whole process group: claude may spawn children that would
        # otherwise orphan and keep stdout/stderr pipes open after proc dies.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            stdout, stderr = proc.communicate()
        except Exception:
            stdout, stderr = "", ""
        finished_at = datetime.now(timezone.utc)
        return RunOutcome(
            status=ResultStatus.TIMEOUT,
            output=stdout or "",
            error=(stderr or None) if stderr else f"Timed out after {timeout_seconds}s",
            started_at=started_at,
            finished_at=finished_at,
            exit_code=proc.returncode,
        )
    except Exception as exc:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        finished_at = datetime.now(timezone.utc)
        return RunOutcome(
            status=ResultStatus.FAILED,
            output="",
            error=f"Subprocess error: {exc}",
            started_at=started_at,
            finished_at=finished_at,
            exit_code=proc.returncode,
        )

    finished_at = datetime.now(timezone.utc)
    exit_code = proc.returncode
    status = ResultStatus.SUCCESS if exit_code == 0 else ResultStatus.FAILED
    error: Optional[str] = None
    if status == ResultStatus.FAILED:
        error = stderr.strip() if stderr and stderr.strip() else f"Exit code {exit_code}"

    output_chars = len(stdout or "")
    estimated_cost_usd = _estimate_cost_usd(input_chars, output_chars)
    return RunOutcome(
        status=status,
        output=stdout or "",
        error=error,
        started_at=started_at,
        finished_at=finished_at,
        exit_code=exit_code,
        input_chars=input_chars,
        output_chars=output_chars,
        estimated_cost_usd=estimated_cost_usd,
    )
