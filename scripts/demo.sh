#!/usr/bin/env bash
# demo.sh — single-command live demo runner for spare-change.
# Usage: ./scripts/demo.sh   (run from repo root)
# Starts distributor, opens dashboard, seeds a Scrapling code-review task,
# runs the donor agent once, then keeps the distributor up until Ctrl-C.
# Logs: /tmp/sc-demo-distributor.log, /tmp/sc-demo-seed.log

set -euo pipefail

DIST_LOG="/tmp/sc-demo-distributor.log"
DIST_PID="/tmp/sc-demo-distributor.pid"
SEED_LOG="/tmp/sc-demo-seed.log"
DASHBOARD_URL="http://127.0.0.1:8080/"
HEALTH_URL="http://127.0.0.1:8080/healthz"

cleanup() {
    if [[ -f "${DIST_PID}" ]]; then
        local pid
        pid="$(cat "${DIST_PID}" 2>/dev/null || true)"
        if [[ -n "${pid}" ]]; then
            kill "${pid}" 2>/dev/null || true
        fi
        rm -f "${DIST_PID}"
    fi
}
trap cleanup EXIT INT TERM

# 1. Kill any prior distributor on port 8080.
lsof -ti:8080 | xargs kill -9 2>/dev/null || true

# 2. Remove stale demo files.
rm -f /tmp/sc-demo-*.log /tmp/sc-demo-*.pid

# 3. Banner.
echo "================================================================"
echo " spare-change live demo"
echo " Distributor → dashboard → seed Scrapling review → donor agent"
echo " Dashboard: ${DASHBOARD_URL}    Ctrl-C to stop."
echo "================================================================"

# 4. Start distributor in background.
echo "▶ Starting distributor on :8080..."
.venv/bin/python -m distributor.main >"${DIST_LOG}" 2>&1 &
echo $! >"${DIST_PID}"

# 5. Wait for /healthz (max 20 × 0.3s).
ready=0
for _ in $(seq 1 20); do
    if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 0.3
done
if [[ "${ready}" -ne 1 ]]; then
    echo "✗ Distributor failed to become healthy. Log:"
    cat "${DIST_LOG}" || true
    exit 1
fi
echo "✓ Distributor healthy."

# 6. Open dashboard.
if command -v open >/dev/null 2>&1; then
    open "${DASHBOARD_URL}" || true
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${DASHBOARD_URL}" || true
else
    echo "Open in browser: ${DASHBOARD_URL}"
fi

# 7. Seed task.
echo "▶ Seeding task: D4Vinci/Scrapling/scrapling/core/mixins.py (review)..."
if ./scripts/seed_from_repo.sh D4Vinci/Scrapling scrapling/core/mixins.py review >"${SEED_LOG}" 2>&1; then
    echo "✓ Task seeded."
else
    echo "✗ Seed failed. Log:"
    cat "${SEED_LOG}" || true
    exit 1
fi

# 8. Run donor agent once (live output).
echo "▶ Donor agent running task..."
.venv/bin/python -m agent.daemon --config config.example.yaml --once

# 9. Final summary banner.
echo ""
echo "================================================================"
echo "✓ Donation complete."
echo "Dashboard: ${DASHBOARD_URL}"
echo "View full result:"
echo "  curl -s http://127.0.0.1:8080/tasks | python3 -m json.tool | less"
echo "================================================================"
echo "Distributor still running. Ctrl-C to stop."

# 10. Keep distributor alive until Ctrl-C.
wait
