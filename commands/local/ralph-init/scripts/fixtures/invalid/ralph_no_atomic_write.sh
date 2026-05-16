#!/usr/bin/env bash
# Invalid: writes current_story.json directly without .tmp+mv atomic pattern.
# Has instance lock and numeric guard, but state writes race on crash.
set -euo pipefail

if [ "$(git branch --show-current)" != "main" ]; then exit 1; fi

PRD_FILE=".ralph/prd.json"
PROMPT_FILE=".ralph/PROMPT.md"
LOCK_FILE=".ralph/current_story.json"
OUT_FILE=".ralph/last_output.txt"
INSTANCE_LOCK=".ralph/.instance"

if [ -f "$INSTANCE_LOCK" ]; then
  other_pid=$(cut -d: -f1 "$INSTANCE_LOCK" 2>/dev/null || echo "")
  if [ -n "$other_pid" ] && kill -0 "$other_pid" 2>/dev/null; then exit 1; fi
fi
echo "$$:$(date +%s)" > "$INSTANCE_LOCK"
trap 'rm -f "$INSTANCE_LOCK"' EXIT

assert_nonneg_int() {
  local name="$1"; local val="$2"
  if ! [[ "$val" =~ ^[0-9]+$ ]]; then exit 1; fi
}

for iter in $(seq 1 10); do
  locked_id="DEMO-01"
  # Direct, non-atomic write — this is the violation:
  echo "{\"id\": \"$locked_id\"}" > "$LOCK_FILE"

  current_branch=$(git branch --show-current)
  if [ "$current_branch" != "main" ]; then break; fi

  pre_passes="x:false"
  set +e
  claude --print --dangerously-skip-permissions --model sonnet < "$PROMPT_FILE" > "$OUT_FILE"
  CLAUDE_EXIT_CODE=$?
  set -e
  assert_nonneg_int "CLAUDE_EXIT_CODE" "$CLAUDE_EXIT_CODE"

  post_passes="x:true"
  if [ "$pre_passes" != "$post_passes" ]; then
    echo "VIOLATION check"
  fi

  grep -q YIELD "$OUT_FILE" || grep -q COMPLETE "$OUT_FILE"
  rm -f "$LOCK_FILE"
done
