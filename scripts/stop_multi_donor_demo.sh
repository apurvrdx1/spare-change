#!/usr/bin/env bash
# Stop a running multi-donor demo by killing PIDs recorded in /tmp/sc-multi-*.pid.
# Idempotent: missing files and dead PIDs are ignored.
# Usage: ./scripts/stop_multi_donor_demo.sh

set -euo pipefail

for pid_file in /tmp/sc-multi-distributor.pid /tmp/sc-multi-donor-alice.pid /tmp/sc-multi-donor-bob.pid /tmp/sc-multi-donor-charlie.pid; do
    if [[ -f "$pid_file" ]]; then
        pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "Killed PID ${pid} (${pid_file})."
        fi
        rm -f "$pid_file"
    fi
done
echo "Multi-donor demo stopped."
