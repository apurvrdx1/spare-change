#!/usr/bin/env bash
# Seed a real OSS file from GitHub as a spare-change task.
#
# Usage:
#   ./scripts/seed_from_repo.sh OWNER/REPO PATH_IN_REPO [KIND]
#
# KIND: annotate (default) | review | test-gen
#
# Examples (small, recognizable files good for demo):
#   ./scripts/seed_from_repo.sh psf/requests src/requests/_internal_utils.py annotate
#   ./scripts/seed_from_repo.sh psf/requests src/requests/help.py review
#   ./scripts/seed_from_repo.sh tornadoweb/tornado tornado/escape.py annotate
#   ./scripts/seed_from_repo.sh httpie/cli httpie/utils.py test-gen
#   ./scripts/seed_from_repo.sh pallets/click src/click/_textwrap.py annotate
#
# Env overrides:
#   BRANCH=main             which branch / ref to pull from (default: HEAD)
#   DISTRIBUTOR_URL=...     distributor base URL (default: http://127.0.0.1:8080)

set -euo pipefail

REPO="${1:?usage: $0 OWNER/REPO PATH_IN_REPO [KIND]}"
FILE_PATH="${2:?usage: $0 OWNER/REPO PATH_IN_REPO [KIND]}"
KIND="${3:-annotate}"
BRANCH="${BRANCH:-HEAD}"
DISTRIBUTOR_URL="${DISTRIBUTOR_URL:-http://127.0.0.1:8080}"

case "$KIND" in
  annotate)
    PROMPT_TEXT="Add comprehensive type annotations to the following Python file. Return only the complete annotated file, no commentary or markdown fences. Use modern Python 3.11+ syntax: \`list[str]\` not \`List[str]\`, \`X | None\` not \`Optional[X]\`. Do not change any logic."
    ;;
  review)
    PROMPT_TEXT="Review the following file for bugs, error-handling gaps, performance issues, and stylistic problems a maintainer would care about. Output a markdown list of findings, each tagged [bug|perf|style|test-gap] with file:line reference and a one-line suggested fix. Be specific and concrete, not generic."
    ;;
  test-gen)
    PROMPT_TEXT="Generate a pytest test module for the following file. Cover the happy path, edge cases, and at least one error path per public function. Use pytest fixtures and \`parametrize\` where appropriate. Return only the test file content, no commentary or fences."
    ;;
  *)
    echo "Unknown KIND: $KIND (expected: annotate | review | test-gen)" >&2
    exit 1
    ;;
esac

RAW_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}/${FILE_PATH}"
echo "Fetching: $RAW_URL" >&2

FILE_CONTENT="$(curl -fsSL "$RAW_URL")"
if [[ -z "$FILE_CONTENT" ]]; then
  echo "Error: empty file content from $RAW_URL" >&2
  exit 1
fi

export REPO FILE_PATH KIND PROMPT_TEXT FILE_CONTENT

PAYLOAD="$(python3 -c '
import json, os
print(json.dumps({
    "project_slug": os.environ["REPO"],
    "prompt": os.environ["PROMPT_TEXT"],
    "context_files": [{
        "path": os.environ["FILE_PATH"],
        "content": os.environ["FILE_CONTENT"],
    }],
    "max_cost_usd": 0.50,
    "timeout_seconds": 180,
    "metadata": {
        "source": "github",
        "repo": os.environ["REPO"],
        "path": os.environ["FILE_PATH"],
        "kind": os.environ["KIND"],
    },
}))
')"

echo "$PAYLOAD" | curl -sf -X POST -H "Content-Type: application/json" \
  -d @- "${DISTRIBUTOR_URL}/tasks" | python3 -m json.tool
