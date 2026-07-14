#!/usr/bin/env bash
set -euo pipefail

# Hard gate: must be on main with clean worktree
if [ "$(git branch --show-current)" != "main" ]; then
  echo "FATAL: must run on main"; exit 1
fi

PRD_FILE=".ralph/prd.json"
PROMPT_FILE=".ralph/PROMPT.md"
LOCK_FILE=".ralph/current_story.json"
OUT_FILE=".ralph/last_output.txt"
INSTANCE_LOCK=".ralph/.instance"

# --- Instance lock (borrowed from ralph-loop plugin session_id pattern) ---
# Prevent two ralph.sh processes from racing on the same .ralph/ state.
if [ -f "$INSTANCE_LOCK" ]; then
  other_pid=$(cut -d: -f1 "$INSTANCE_LOCK" 2>/dev/null || echo "")
  if [ -n "$other_pid" ] && [ "$other_pid" != "$$" ] && kill -0 "$other_pid" 2>/dev/null; then
    echo "FATAL: another ralph instance is running (pid=$other_pid)"
    echo "  If you are sure no other instance is running, remove $INSTANCE_LOCK"
    exit 1
  fi
fi
echo "$$:$(date +%s)" > "$INSTANCE_LOCK"
trap 'rm -f "$INSTANCE_LOCK"' EXIT

# --- Numeric guard helper (borrowed from ralph-loop stop-hook.sh) ---
# Any value read from a state file must be regex-validated before arithmetic.
assert_nonneg_int() {
  local name="$1"
  local val="$2"
  if ! [[ "$val" =~ ^[0-9]+$ ]]; then
    echo "FATAL: $name must be a non-negative integer (got: '$val')"
    exit 1
  fi
}

# --- Atomic state write helper ---
# Prevent half-written state files on Ctrl+C or crash.
atomic_write() {
  local target="$1"
  local content="$2"
  local tmp="${target}.tmp.$$"
  printf '%s' "$content" > "$tmp"
  mv "$tmp" "$target"
}

for iter in $(seq 1 10); do
  locked_id=$(python3 -c "
import json
data = json.load(open('$PRD_FILE'))
for s in data['userStories']:
    if not s['passes']:
        print(s['id'])
        break
")
  if [ -z "$locked_id" ]; then
    echo "all stories complete"
    exit 0
  fi
  atomic_write "$LOCK_FILE" "{\"id\": \"$locked_id\"}"

  # Assert still on target branch (agent may have switched in previous iteration)
  current_branch=$(git branch --show-current)
  if [ "$current_branch" != "main" ]; then
    echo "FATAL: no longer on main (now on $current_branch)."
    break
  fi

  pre_passes=$(python3 -c "
import json
d = json.load(open('$PRD_FILE'))
print(' '.join(f\"{s['id']}:{s['passes']}\" for s in d['userStories']))
")

  set +e
  claude --print --dangerously-skip-permissions --model sonnet < "$PROMPT_FILE" > "$OUT_FILE"
  CLAUDE_EXIT_CODE=$?
  set -e
  assert_nonneg_int "CLAUDE_EXIT_CODE" "$CLAUDE_EXIT_CODE"

  post_passes=$(python3 -c "
import json
d = json.load(open('$PRD_FILE'))
print(' '.join(f\"{s['id']}:{s['passes']}\" for s in d['userStories']))
")

  python3 - "$locked_id" "$pre_passes" "$post_passes" <<'PY'
import sys
locked = sys.argv[1]
pre = dict(tok.split(':') for tok in sys.argv[2].split())
post = dict(tok.split(':') for tok in sys.argv[3].split())
for sid, pre_val in pre.items():
    if pre_val != post[sid] and sid != locked:
        print(f"VIOLATION: {sid} passes changed outside lock")
        sys.exit(2)
    if sid == locked and pre_val == "True" and post[sid] == "False":
        print("VIOLATION: locked story regressed from true to false")
        sys.exit(2)
PY

  if [ -f "$OUT_FILE" ] && grep -q "<promise>COMPLETE</promise>" "$OUT_FILE"; then
    echo "agent claims COMPLETE, cross-check prd"
  fi

  if [ "$CLAUDE_EXIT_CODE" -ne 0 ]; then
    echo "claude failed with exit $CLAUDE_EXIT_CODE"
    exit "$CLAUDE_EXIT_CODE"
  fi

  rm -f "$LOCK_FILE"

  if [ -f "$OUT_FILE" ] && grep -q YIELD "$OUT_FILE"; then
    continue
  fi
done
