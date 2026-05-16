#!/usr/bin/env bash
# Structural diff wiring is entirely missing.
set -euo pipefail

PRD_FILE=".ralph/prd.json"
LOCK_FILE=".ralph/current_story.json"

echo "{\"id\": \"DEMO-01\"}" > "$LOCK_FILE"
set +e
claude --print --dangerously-skip-permissions --model sonnet < .ralph/PROMPT.md
CLAUDE_EXIT_CODE=$?
set -e
grep -q YIELD .ralph/last_output.txt
grep -q COMPLETE .ralph/last_output.txt
echo "VIOLATION branch exists but no comparison is ever done"
rm -f "$LOCK_FILE"
