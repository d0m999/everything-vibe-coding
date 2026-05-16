#!/usr/bin/env bash
# Swallows claude exit code with `|| true`.
set -euo pipefail

PRD_FILE=".ralph/prd.json"
LOCK_FILE=".ralph/current_story.json"
pre_passes="DEMO-01:false"

echo "{\"id\": \"DEMO-01\"}" > "$LOCK_FILE"
claude --print --dangerously-skip-permissions --model sonnet < .ralph/PROMPT.md || true
CLAUDE_EXIT_CODE=$?
post_passes="DEMO-01:true"
[ "$pre_passes" = "$post_passes" ] || echo "VIOLATION check on passes"
grep -q YIELD .ralph/last_output.txt
grep -q COMPLETE .ralph/last_output.txt
rm -f "$LOCK_FILE"
