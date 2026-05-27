"""Queue spare-change tasks from a manifest file.

Usage:
    python scripts/queue_spare_change_tasks.py --manifest .github/spare-change-manifest.yaml
    python scripts/queue_spare_change_tasks.py --manifest manifest.json --dry-run
"""

import argparse
import base64  # noqa: F401  (reserved for future auth schemes)
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

# Prompts mirror scripts/seed_from_repo.sh in the spare-change repo so that
# donor-side workers see consistent instructions regardless of seed path.
PROMPT_ANNOTATE = (
    "Add comprehensive type annotations to the following Python file. "
    "Return only the complete annotated file, no commentary or markdown fences. "
    "Use modern Python 3.11+ syntax: `list[str]` not `List[str]`, "
    "`X | None` not `Optional[X]`. Do not change any logic."
)

PROMPT_REVIEW = (
    "Review the following file for bugs, error-handling gaps, performance "
    "issues, and stylistic problems a maintainer would care about. Output a "
    "markdown list of findings, each tagged [bug|perf|style|test-gap] with "
    "file:line reference and a one-line suggested fix. Be specific and "
    "concrete, not generic."
)

PROMPT_TEST_GEN = (
    "Generate a pytest test module for the following file. Cover the happy "
    "path, edge cases, and at least one error path per public function. Use "
    "pytest fixtures and `parametrize` where appropriate. Return only the "
    "test file content, no commentary or fences."
)

KIND_TO_PROMPT = {
    "annotate": PROMPT_ANNOTATE,
    "review": PROMPT_REVIEW,
    "test-gen": PROMPT_TEST_GEN,
}

DEFAULT_MAX_COST_USD = 0.50
DEFAULT_TIMEOUT_SECONDS = 180


def detect_repo_slug() -> str | None:
    """Return owner/repo from `git remote get-url origin`, or None on failure."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    # Accept git@github.com:owner/repo(.git) and https://github.com/owner/repo(.git)
    if url.startswith("git@"):
        _, _, path = url.partition(":")
    else:
        path = url.split("github.com/", 1)[-1]
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.strip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return None


def load_manifest(path: str) -> list[dict]:
    """Load a manifest from YAML or JSON. YAML requires PyYAML."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError:
            sys.exit(
                "ERROR: manifest is YAML but PyYAML is not installed. "
                "Install with `pip install pyyaml`, or use a .json manifest."
            )
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if not isinstance(data, list):
        sys.exit("ERROR: manifest must be a list of {path, kind} entries.")
    return data


def build_payload(entry: dict, repo_slug: str) -> dict:
    """Convert one manifest entry into a /tasks POST body."""
    file_path = entry.get("path")
    kind = entry.get("kind", "annotate")
    if not file_path:
        raise ValueError(f"manifest entry missing 'path': {entry!r}")
    if kind not in KIND_TO_PROMPT:
        raise ValueError(
            f"manifest entry has unknown kind {kind!r} "
            f"(expected one of {sorted(KIND_TO_PROMPT)})"
        )
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"manifest path not found on disk: {file_path}")
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    return {
        "project_slug": repo_slug,
        "prompt": KIND_TO_PROMPT[kind],
        "context_files": [{"path": file_path, "content": content}],
        "max_cost_usd": entry.get("max_cost_usd", DEFAULT_MAX_COST_USD),
        "timeout_seconds": entry.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        "metadata": {
            "source": "maintainer-kit",
            "repo": repo_slug,
            "path": file_path,
            "kind": kind,
        },
    }


def post_task(distributor: str, token: str, payload: dict) -> dict:
    """POST one task to {distributor}/tasks and return the decoded response."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{distributor.rstrip('/')}/tasks",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            sys.exit(
                f"ERROR: distributor rejected the bearer token ({exc.code}). "
                "Check SPARE_CHANGE_DISTRIBUTOR_TOKEN."
            )
        sys.exit(f"ERROR: distributor returned HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError as exc:
        sys.exit(f"ERROR: could not reach distributor at {distributor}: {exc.reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue spare-change tasks from a manifest.")
    parser.add_argument("--manifest", required=True, help="Path to YAML or JSON manifest.")
    parser.add_argument("--distributor", default="http://127.0.0.1:8080", help="Distributor base URL.")
    parser.add_argument(
        "--token",
        default=os.environ.get("SPARE_CHANGE_DISTRIBUTOR_TOKEN", ""),
        help="Bearer token (defaults to $SPARE_CHANGE_DISTRIBUTOR_TOKEN).",
    )
    parser.add_argument("--repo", default=None, help="owner/repo slug (auto-detected from git remote).")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without POSTing.")
    args = parser.parse_args()

    repo_slug = args.repo or detect_repo_slug()
    if not repo_slug:
        sys.exit("ERROR: could not detect repo slug. Pass --repo owner/name.")

    if not args.dry_run and not args.token:
        sys.exit("ERROR: no token provided. Set --token or SPARE_CHANGE_DISTRIBUTOR_TOKEN.")

    entries = load_manifest(args.manifest)
    if not entries:
        print("manifest is empty; nothing to do.", file=sys.stderr)
        return 0

    failures = 0
    for entry in entries:
        try:
            payload = build_payload(entry, repo_slug)
        except (ValueError, FileNotFoundError) as exc:
            print(f"SKIP {entry!r}: {exc}", file=sys.stderr)
            failures += 1
            continue
        if args.dry_run:
            print(json.dumps({"would_post": payload}, indent=2))
            continue
        result = post_task(args.distributor, args.token, payload)
        task_id = result.get("task_id") or result.get("id") or "<unknown>"
        print(f"queued {entry['path']} ({entry.get('kind', 'annotate')}) -> task_id={task_id}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
