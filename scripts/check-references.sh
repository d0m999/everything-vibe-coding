#!/usr/bin/env bash
# check-references.sh — flag dangling cross-references in vendored files
#
# Strategy:
#   - Build "drop set" = (all ecc names) - (v1 keep names)
#   - For each drop name, grep its literal occurrence in vendored files
#   - Skips short names (< 7 chars) to avoid false positives on common words
#
# Run after vendor-from-ecc.sh --apply, before install.sh.

set -uo pipefail   # NOTE: no -e — grep returning 1 on no match is normal

ECC_ROOT="${ECC_ROOT:-$HOME/.claude/plugins/marketplaces/ecc}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIN_NAME_LEN=7   # below this length → too generic, skip to avoid false positives

cd "$REPO_ROOT"

# ===== Build v1 keep name set =====
KEEP_FILE="/tmp/v1-keep.$$"
{
  ls agents/*.md 2>/dev/null   | xargs -n1 basename | sed 's/\.md$//'
  ls -d skills/*/ 2>/dev/null  | xargs -n1 basename
  ls commands/*.md 2>/dev/null | xargs -n1 basename | sed 's/\.md$//'
  echo "plan-orchestrate"
  echo "ralph-init"
} | sort -u > "$KEEP_FILE"

KEEP_COUNT=$(wc -l < "$KEEP_FILE" | tr -d ' ')

# ===== Build ecc full name set =====
ECC_FILE="/tmp/ecc-all.$$"
{
  ls "$ECC_ROOT/agents/"*.md 2>/dev/null   | xargs -n1 basename | sed 's/\.md$//'
  ls -d "$ECC_ROOT/skills/"*/ 2>/dev/null  | xargs -n1 basename
  ls "$ECC_ROOT/commands/"*.md 2>/dev/null | xargs -n1 basename | sed 's/\.md$//'
} | sort -u > "$ECC_FILE"

ECC_COUNT=$(wc -l < "$ECC_FILE" | tr -d ' ')

# ===== Drop set = ecc - keep =====
DROP_FILE="/tmp/v1-drop.$$"
comm -23 "$ECC_FILE" "$KEEP_FILE" > "$DROP_FILE"
DROP_COUNT=$(wc -l < "$DROP_FILE" | tr -d ' ')

# Filter out short names (would be too generic / many false positives)
DROP_LONG="/tmp/v1-drop-long.$$"
awk -v min=$MIN_NAME_LEN 'length($0) >= min' "$DROP_FILE" > "$DROP_LONG"
DROP_LONG_COUNT=$(wc -l < "$DROP_LONG" | tr -d ' ')

echo "==> check-references.sh"
echo "    v1 keep set:           $KEEP_COUNT names"
echo "    ecc full set:          $ECC_COUNT names"
echo "    drop set (ecc - keep): $DROP_COUNT names"
echo "    scanning drop names with length >= $MIN_NAME_LEN: $DROP_LONG_COUNT names"
echo

# ===== Scan =====
HITS_FILE="/tmp/v1-hits.$$"
: > "$HITS_FILE"

while IFS= read -r name; do
  # Match the name as a "word" (boundary) — \b doesn't work in BSD grep, use ERE
  # Pattern: surround with non-name-char or BOL/EOL
  matches=$(grep -rnE "(^|[^a-z0-9_-])$name([^a-z0-9_-]|$)" \
    agents/ skills/ commands/ 2>/dev/null || true)
  if [[ -n "$matches" ]]; then
    while IFS= read -r m; do
      # m format: file:lineno:content
      printf '%s\t%s\n' "$name" "$m" >> "$HITS_FILE"
    done <<< "$matches"
  fi
done < "$DROP_LONG"

# ===== Report =====
HIT_LINES=$(wc -l < "$HITS_FILE" | tr -d ' ')
UNIQUE_DROP_HIT=$(awk -F'\t' '{print $1}' "$HITS_FILE" | sort -u | grep -c . 2>/dev/null || echo 0)

if [[ "$HIT_LINES" -eq 0 ]]; then
  echo "==> No dangling references detected."
  rm -f "$KEEP_FILE" "$ECC_FILE" "$DROP_FILE" "$DROP_LONG" "$HITS_FILE"
  exit 0
fi

VERBOSE=false
for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE=true ;;
  esac
done

echo "==> Dangling references summary"
echo
echo "## Unique drop names referenced in vendored files (sorted by count)"
echo "   Low count (≤3) is more likely a real dangling ref."
echo "   High count (>10) is likely a false positive (common word)."
echo
awk -F'\t' '{print $1}' "$HITS_FILE" | sort | uniq -c | sort -rn | \
  awk '{printf "  %4d  %s\n", $1, $2}'
echo
echo "==> Stats"
echo "    Drop-list name reference lines: $HIT_LINES"
echo "    Unique drop names hit:          $UNIQUE_DROP_HIT"
echo

# ===== Heuristic classification =====
echo "==> Heuristic classification"
LIKELY_FP=$(awk -F'\t' '{print $1}' "$HITS_FILE" | sort | uniq -c | awk '$1 > 10 {print $2}' | wc -l | tr -d ' ')
LIKELY_REAL=$(awk -F'\t' '{print $1}' "$HITS_FILE" | sort | uniq -c | awk '$1 <= 3 {print $2}' | wc -l | tr -d ' ')
MIDDLE=$(awk -F'\t' '{print $1}' "$HITS_FILE" | sort | uniq -c | awk '$1 > 3 && $1 <= 10 {print $2}' | wc -l | tr -d ' ')
echo "    Likely false positives (count > 10, common words):  $LIKELY_FP"
echo "    Uncertain (count 4-10, needs review):                $MIDDLE"
echo "    Likely real dangling refs (count ≤ 3):               $LIKELY_REAL"
echo

if [[ "$VERBOSE" == "true" ]]; then
  echo "==> Verbose: all hit locations"
  echo
  awk -F'\t' '
  {
    name=$1
    rest=$2
    refs[name] = refs[name] "      " rest "\n"
    count[name]++
  }
  END {
    for (n in count) printf "  %s (%d):\n%s\n", n, count[n], refs[n]
  }' "$HITS_FILE" | sort
fi

echo
echo "Resolution per hit:"
echo "  1. Promote drop name to v1 keep (re-vendor with it)"
echo "  2. Edit the file to remove or replace the reference"
echo "  3. Accept (false positive — note in docs/UPSTREAM.md)"
echo
echo "(Run with --verbose to see all hit locations)"
echo "(Note: text-only mentions don't break install; ecc plugin runtime"
echo "       resolution only triggers on real Agent/Task tool calls.)"

rm -f "$KEEP_FILE" "$ECC_FILE" "$DROP_FILE" "$DROP_LONG" "$HITS_FILE"
exit 1
