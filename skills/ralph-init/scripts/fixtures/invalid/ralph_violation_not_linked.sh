#!/usr/bin/env bash
# Structural diff is declared far from the stop branch.
set -euo pipefail

PRD_FILE=".ralph/prd.json"
LOCK_FILE=".ralph/current_story.json"
pre_passes="DEMO-01:false"
before_snapshot="saved"

echo "{\"id\": \"DEMO-01\"}" > "$LOCK_FILE"
set +e
claude --print --dangerously-skip-permissions --model sonnet < .ralph/PROMPT.md > .ralph/last_output.txt
CLAUDE_EXIT_CODE=$?
set -e

echo "filler line 01"
echo "filler line 02"
echo "filler line 03"
echo "filler line 04"
echo "filler line 05"
echo "filler line 06"
echo "filler line 07"
echo "filler line 08"
echo "filler line 09"
echo "filler line 10"
echo "filler line 11"
echo "filler line 12"
echo "filler line 13"
echo "filler line 14"
echo "filler line 15"
echo "filler line 16"
echo "filler line 17"
echo "filler line 18"
echo "filler line 19"
echo "filler line 20"
echo "filler line 21"
echo "filler line 22"
echo "filler line 23"
echo "filler line 24"
echo "filler line 25"
echo "filler line 26"
echo "filler line 27"
echo "filler line 28"
echo "filler line 29"
echo "filler line 30"
echo "filler line 31"
echo "filler line 32"
echo "filler line 33"
echo "filler line 34"
echo "filler line 35"
echo "filler line 36"
echo "filler line 37"
echo "filler line 38"
echo "filler line 39"
echo "filler line 40"
echo "filler line 41"
echo "filler line 42"
echo "filler line 43"
echo "filler line 44"
echo "filler line 45"

grep -q YIELD .ralph/last_output.txt
grep -q COMPLETE .ralph/last_output.txt
echo "VIOLATION dangling here"
rm -f "$LOCK_FILE"
