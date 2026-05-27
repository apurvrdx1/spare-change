#!/usr/bin/env bash
# Seed a type-annotation task into a running distributor.
# Usage: run from repo root. Override target with DISTRIBUTOR_URL=http://host:port.

set -euo pipefail

SAMPLE_FILE="examples/untyped_sample.py"
DISTRIBUTOR_URL="${DISTRIBUTOR_URL:-http://127.0.0.1:8080}"

if [ ! -f "$SAMPLE_FILE" ]; then
    echo "Error: $SAMPLE_FILE not found. Run from repo root." >&2
    exit 1
fi

PAYLOAD=$(python3 -c '
import json
import sys

with open("examples/untyped_sample.py", "r") as f:
    content = f.read()

payload = {
    "project_slug": "psf/requests",
    "prompt": (
        "Add comprehensive type annotations to the following Python file. "
        "Return the complete annotated file. Use modern Python 3.11+ syntax "
        "(`list[str]` not `List[str]`, `X | None` not `Optional[X]`). "
        "Do not change any logic. Only add types."
    ),
    "context_files": [
        {"path": "examples/untyped_sample.py", "content": content}
    ],
    "max_cost_usd": 0.25,
    "timeout_seconds": 120,
}

json.dump(payload, sys.stdout)
')

RESPONSE=$(printf '%s' "$PAYLOAD" | curl -s -X POST \
    -H "Content-Type: application/json" \
    -d @- \
    "${DISTRIBUTOR_URL}/tasks")

CURL_EXIT=$?
if [ $CURL_EXIT -ne 0 ]; then
    echo "curl failed with exit code $CURL_EXIT" >&2
    exit $CURL_EXIT
fi

printf '%s' "$RESPONSE" | python3 -m json.tool
