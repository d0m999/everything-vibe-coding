#!/usr/bin/env bash
# Invalid: missing instance lock (no .ralph/.instance, no kill -0, no trap EXIT).
# All other mechanisms present.
set -euo pipefail

if [ "$(git branch --show-current)" != "main" ]; then
  echo "FATAL: must run on main"; exit 1
fi

PRD_FILE=".ralph/prd.json"
PROMPT_FILE=".ralph/PROMPT.md"
LOCK_FILE=".ralph/current_story.json"
OUT_FILE=".ralph/last_output.txt"

assert_nonneg_int() {
  local name="$1"; local val="$2"
  if ! [[ "$val" =~ ^[0-9]+$ ]]; then
    echo "FATAL: $name not int"; exit 1
  fi
}
atomic_write() {
  local t="$1.tmp.$$"; printf '%s' "$2" > "$t"; mv "$t" "$1"
}

for iter in $(seq 1 10); do
  locked_id="DEMO-01"
  atomic_write "$LOCK_FILE" "{\"id\": \"$locked_id\"}"

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
    echo "VIOLATION check: compare passes"
  fi

  grep -q YIELD "$OUT_FILE" || grep -q COMPLETE "$OUT_FILE"
  rm -f "$LOCK_FILE"
done
