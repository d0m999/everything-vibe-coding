#!/usr/bin/env bash
# Regression runner for the three ralph-init validators.
#
# Each fixture is an input that the validator must accept (valid/) or
# reject (invalid/). The runner prints a tally and exits non-zero if any
# case behaves unexpectedly.
#
# Usage: bash scripts/run_fixtures.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
VALIDATE_PRD="python3 $SCRIPT_DIR/validate_prd.py"
VALIDATE_PROMPT="python3 $SCRIPT_DIR/validate_prompt.py"
VALIDATE_RALPH="python3 $SCRIPT_DIR/validate_ralph.py"

pass=0
fail=0
failed_cases=()

run_case() {
  local label="$1"
  local cmd="$2"
  local fixture="$3"
  local expect="$4"  # "pass" or "fail"

  local output
  output=$($cmd "$fixture" 2>&1)
  local rc=$?

  local ok=false
  if [ "$expect" = "pass" ] && [ "$rc" -eq 0 ]; then
    ok=true
  elif [ "$expect" = "fail" ] && [ "$rc" -ne 0 ]; then
    ok=true
  fi

  if $ok; then
    pass=$((pass + 1))
    printf "  OK   %-55s (%s)\n" "$label" "$expect"
  else
    fail=$((fail + 1))
    failed_cases+=("$label")
    printf "  FAIL %-55s (expected %s, got rc=%s)\n" "$label" "$expect" "$rc"
    printf "       output: %s\n" "$output"
  fi
}

echo "validate_prd.py"
run_case "valid/prd.json"                    "$VALIDATE_PRD"    "$FIXTURES_DIR/valid/prd.json"                       "pass"
run_case "invalid/prd_missing_toplevel.json" "$VALIDATE_PRD"    "$FIXTURES_DIR/invalid/prd_missing_toplevel.json"    "fail"
run_case "invalid/prd_duplicate_id.json"     "$VALIDATE_PRD"    "$FIXTURES_DIR/invalid/prd_duplicate_id.json"        "fail"
run_case "invalid/prd_bad_priority.json"     "$VALIDATE_PRD"    "$FIXTURES_DIR/invalid/prd_bad_priority.json"        "fail"
run_case "invalid/prd_passes_true.json"      "$VALIDATE_PRD"    "$FIXTURES_DIR/invalid/prd_passes_true.json"         "fail"
run_case "invalid/prd_bad_storytype.json"    "$VALIDATE_PRD"    "$FIXTURES_DIR/invalid/prd_bad_storytype.json"       "fail"
run_case "invalid/prd_empty_acceptance.json" "$VALIDATE_PRD"    "$FIXTURES_DIR/invalid/prd_empty_acceptance.json"    "fail"

echo ""
echo "validate_prompt.py"
run_case "valid/PROMPT.txt"                  "$VALIDATE_PROMPT" "$FIXTURES_DIR/valid/PROMPT.txt"                     "pass"
run_case "invalid/prompt_template_var.txt"   "$VALIDATE_PROMPT" "$FIXTURES_DIR/invalid/prompt_template_var.txt"      "fail"
run_case "invalid/prompt_double_brace.txt"   "$VALIDATE_PROMPT" "$FIXTURES_DIR/invalid/prompt_double_brace.txt"      "fail"
run_case "invalid/prompt_missing_yield.txt"  "$VALIDATE_PROMPT" "$FIXTURES_DIR/invalid/prompt_missing_yield.txt"     "fail"
run_case "invalid/prompt_missing_anti_cheat.txt" "$VALIDATE_PROMPT" "$FIXTURES_DIR/invalid/prompt_missing_anti_cheat.txt" "fail"

echo ""
echo "validate_ralph.py"
run_case "valid/ralph.sh"                    "$VALIDATE_RALPH"  "$FIXTURES_DIR/valid/ralph.sh"                       "pass"
run_case "invalid/ralph_no_snapshot.sh"      "$VALIDATE_RALPH"  "$FIXTURES_DIR/invalid/ralph_no_snapshot.sh"         "fail"
run_case "invalid/ralph_forbidden_timeout.sh" "$VALIDATE_RALPH" "$FIXTURES_DIR/invalid/ralph_forbidden_timeout.sh"   "fail"
run_case "invalid/ralph_or_true.sh"          "$VALIDATE_RALPH"  "$FIXTURES_DIR/invalid/ralph_or_true.sh"             "fail"
run_case "invalid/ralph_missing_print.sh"    "$VALIDATE_RALPH"  "$FIXTURES_DIR/invalid/ralph_missing_print.sh"       "fail"
run_case "invalid/ralph_violation_not_linked.sh" "$VALIDATE_RALPH" "$FIXTURES_DIR/invalid/ralph_violation_not_linked.sh" "fail"
run_case "invalid/ralph_no_instance_lock.sh" "$VALIDATE_RALPH"  "$FIXTURES_DIR/invalid/ralph_no_instance_lock.sh"    "fail"
run_case "invalid/ralph_no_atomic_write.sh"  "$VALIDATE_RALPH"  "$FIXTURES_DIR/invalid/ralph_no_atomic_write.sh"     "fail"
run_case "invalid/ralph_no_numeric_guard.sh" "$VALIDATE_RALPH"  "$FIXTURES_DIR/invalid/ralph_no_numeric_guard.sh"    "fail"

echo ""
total=$((pass + fail))
echo "result: $pass/$total passed"
if [ "$fail" -gt 0 ]; then
  echo "failed cases:"
  for c in "${failed_cases[@]}"; do echo "  - $c"; done
  exit 1
fi
