#!/usr/bin/env bash
# Run the spare-change multi-donor demo: 1 distributor + 3 donor agents in parallel,
# seeded with a batch of Scrapling code-review tasks. Run from the repo root.
# Usage: ./scripts/run_multi_donor_demo.sh
# Stop with Ctrl-C (trap cleans up all processes) or ./scripts/stop_multi_donor_demo.sh.

set -euo pipefail

REPO_ROOT="$(pwd)"
VENV_PY="${REPO_ROOT}/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
    echo "ERROR: ${VENV_PY} not found or not executable." >&2
    echo "Create a virtualenv at .venv/ and install the project before running this demo." >&2
    exit 1
fi

DIST_LOG=/tmp/sc-multi-distributor.log
DIST_PID_FILE=/tmp/sc-multi-distributor.pid
ALICE_LOG=/tmp/sc-multi-donor-alice.log
BOB_LOG=/tmp/sc-multi-donor-bob.log
CHARLIE_LOG=/tmp/sc-multi-donor-charlie.log
ALICE_PID_FILE=/tmp/sc-multi-donor-alice.pid
BOB_PID_FILE=/tmp/sc-multi-donor-bob.pid
CHARLIE_PID_FILE=/tmp/sc-multi-donor-charlie.pid

cleanup() {
    echo ""
    echo "Shutting down multi-donor demo..."
    for pid_file in "$DIST_PID_FILE" "$ALICE_PID_FILE" "$BOB_PID_FILE" "$CHARLIE_PID_FILE"; do
        if [[ -f "$pid_file" ]]; then
            pid="$(cat "$pid_file" 2>/dev/null || true)"
            if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
            rm -f "$pid_file"
        fi
    done
}
trap cleanup EXIT INT TERM

# 1. Start distributor.
echo "Starting distributor..."
: > "$DIST_LOG"
"$VENV_PY" -m distributor.main >> "$DIST_LOG" 2>&1 &
DIST_PID=$!
echo "$DIST_PID" > "$DIST_PID_FILE"

# 2. Wait for distributor to be ready.
ATTEMPT=0
MAX_ATTEMPTS=10
until curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/tasks 2>/dev/null | grep -q "^200$"; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
        echo "ERROR: distributor did not become ready after ${MAX_ATTEMPTS} attempts." >&2
        echo "See ${DIST_LOG} for details." >&2
        exit 1
    fi
    sleep 0.5
done
echo "Distributor is up (PID ${DIST_PID})."

# 3. Start the three donor agents.
start_donor() {
    local name="$1" config="$2" log="$3" pid_file="$4"
    : > "$log"
    "$VENV_PY" -m agent.daemon --config "$config" >> "$log" 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    echo "Started donor ${name} (PID ${pid}) using ${config}."
}

start_donor alice   "${REPO_ROOT}/config.donor-alice.yaml"   "$ALICE_LOG"   "$ALICE_PID_FILE"
start_donor bob     "${REPO_ROOT}/config.donor-bob.yaml"     "$BOB_LOG"     "$BOB_PID_FILE"
start_donor charlie "${REPO_ROOT}/config.donor-charlie.yaml" "$CHARLIE_LOG" "$CHARLIE_PID_FILE"

# 4. Seed 5 Scrapling tasks. Varied paths/kinds so each donor sees different output.
echo ""
echo "Seeding 5 Scrapling tasks..."
TASKS=(
    "scrapling/core/mixins.py review"
    "scrapling/core/translator.py annotate"
    "scrapling/core/storage.py review"
    "scrapling/core/_types.py annotate"
    "scrapling/core/mixins.py test-gen"
)
for entry in "${TASKS[@]}"; do
    # shellcheck disable=SC2086
    set -- $entry
    path="$1"
    kind="$2"
    echo "  -> ${path} (${kind})"
    "${REPO_ROOT}/scripts/seed_from_repo.sh" D4Vinci/Scrapling "$path" "$kind" >/dev/null
done

echo ""
echo "================================================================"
echo " 5 tasks seeded; donors are processing in parallel."
echo " Distributor: PID $(cat "$DIST_PID_FILE")"
echo " Donors:      alice=$(cat "$ALICE_PID_FILE")  bob=$(cat "$BOB_PID_FILE")  charlie=$(cat "$CHARLIE_PID_FILE")"
echo " Logs:        /tmp/sc-multi-*.log"
echo " Ctrl-C to stop (trap will clean up all processes)."
echo "================================================================"
echo ""

# 5. Tail all 4 logs with file-name headers. Block until Ctrl-C.
tail -n +1 -f "$DIST_LOG" "$ALICE_LOG" "$BOB_LOG" "$CHARLIE_LOG"
