#!/usr/bin/env bash
# Uses the forbidden `claude -p` short form and also lacks `--print`.
set -euo pipefail

PRD_FILE=".ralph/prd.json"
LOCK_FILE=".ralph/current_story.json"
pre_passes="DEMO-01:false"

echo "{\"id\": \"DEMO-01\"}" > "$LOCK_FILE"
set +e
claude -p --dangerously-skip-permissions --model sonnet < .ralph/PROMPT.md
CLAUDE_EXIT_CODE=$?
set -e
post_passes="DEMO-01:true"
[ "$pre_passes" = "$post_passes" ] || echo "VIOLATION check on passes"
grep -q YIELD .ralph/last_output.txt
grep -q COMPLETE .ralph/last_output.txt
rm -f "$LOCK_FILE"
