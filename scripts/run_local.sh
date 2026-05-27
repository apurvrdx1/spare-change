#!/usr/bin/env bash
# Run the distributor and agent locally for a development demo.
# Usage: run from repo root with a .venv present and config.example.yaml available.

set -euo pipefail

source .venv/bin/activate

python -m distributor.main &
DISTRIBUTOR_PID=$!

cleanup() {
    if kill -0 "$DISTRIBUTOR_PID" 2>/dev/null; then
        kill "$DISTRIBUTOR_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

sleep 2

ATTEMPT=0
MAX_ATTEMPTS=10
until curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/tasks | grep -q "^200$"; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
        echo "Distributor did not become ready after $MAX_ATTEMPTS attempts." >&2
        exit 1
    fi
    sleep 0.5
done

python -m agent.daemon --config config.example.yaml
