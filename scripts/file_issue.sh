#!/usr/bin/env bash
# Take a completed spare-change task and open a draft GitHub issue with the result.
#
# Usage:
#   ./scripts/file_issue.sh <task_id> [OWNER/REPO]
#
# OWNER/REPO is optional. If omitted, the script reads the task's project_slug
# from the distributor and uses that. Set DISTRIBUTOR_URL to point elsewhere.
#
# Behavior: fetches /tasks/<task_id>/issue.md, shows the title + body for review,
# and (after y/n confirmation) runs `gh issue create` against the chosen repo.
# Requires the `gh` CLI to be authenticated (`gh auth login`).

set -euo pipefail

TASK_ID="${1:?usage: $0 <task_id> [OWNER/REPO]}"
DISTRIBUTOR_URL="${DISTRIBUTOR_URL:-http://127.0.0.1:8080}"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: GitHub CLI (gh) not found. Install from https://cli.github.com" >&2
  exit 1
fi

# Pull title from the response header and body from the response body.
TMP_BODY="$(mktemp)"
TMP_HEAD="$(mktemp)"
trap 'rm -f "$TMP_BODY" "$TMP_HEAD"' EXIT

HTTP_STATUS="$(curl -sS -o "$TMP_BODY" -D "$TMP_HEAD" -w "%{http_code}" \
  "${DISTRIBUTOR_URL%/}/tasks/${TASK_ID}/issue.md")"

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "error: distributor returned HTTP $HTTP_STATUS" >&2
  cat "$TMP_BODY" >&2
  exit 1
fi

TITLE="$(grep -i '^X-Spare-Change-Issue-Title:' "$TMP_HEAD" | head -1 | sed 's/^[^:]*: //' | tr -d '\r')"
if [[ -z "$TITLE" ]]; then
  TITLE="[spare-change] generated task result"
fi

REPO="${2:-}"
if [[ -z "$REPO" ]]; then
  REPO="$(curl -sS "${DISTRIBUTOR_URL%/}/tasks/${TASK_ID}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["task"]["project_slug"])')"
fi

echo "─────────────────────────────────────────────────────────────────"
echo " Repo:  $REPO"
echo " Title: $TITLE"
echo "─────────────────────────────────────────────────────────────────"
echo
head -20 "$TMP_BODY"
echo
echo "... (body is $(wc -c < "$TMP_BODY") bytes total)"
echo
read -r -p "File this as a GitHub issue? [y/N] " REPLY
case "$REPLY" in
  y|Y|yes|YES)
    gh issue create --repo "$REPO" --title "$TITLE" --body-file "$TMP_BODY"
    ;;
  *)
    echo "Cancelled. Markdown body saved to: $TMP_BODY"
    trap - EXIT  # don't delete it so user can grab it
    ;;
esac
