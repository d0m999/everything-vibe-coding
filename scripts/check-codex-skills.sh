#!/usr/bin/env bash
# Deterministically validate the Codex manifest, adapters, policies, and catalog budget.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${EVC_CODEX_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
MANIFEST="${EVC_CODEX_MANIFEST:-$REPO_ROOT/codex-skills.tsv}"
OUT_DIR="${EVC_CODEX_ADAPTER_OUT:-$REPO_ROOT/.agents/skills}"
BUDGET_LIMIT=5000

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/evc-codex-check.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
expected_dir="$tmp_dir/expected"

EVC_CODEX_REPO_ROOT="$REPO_ROOT" \
EVC_CODEX_MANIFEST="$MANIFEST" \
EVC_CODEX_ADAPTER_OUT="$expected_dir" \
  "$SCRIPT_DIR/generate-codex-skills.sh" >/dev/null

if [[ ! -d "$OUT_DIR" ]]; then
  echo "ERROR: generated adapter directory is missing: $OUT_DIR" >&2
  echo "Run ./scripts/generate-codex-command-skills.sh first." >&2
  exit 1
fi

if ! diff -ru "$expected_dir" "$OUT_DIR" >"$tmp_dir/adapter-diff"; then
  echo "ERROR: generated Codex adapters have drifted:" >&2
  cat "$tmp_dir/adapter-diff" >&2
  exit 1
fi

absolute_catalog="$tmp_dir/catalog-absolute"
alias_catalog="$tmp_dir/catalog-root-alias"
: >"$absolute_catalog"
: >"$alias_catalog"
implicit_count=0
adapter_count=0
while IFS=$'\t' read -r name mode description; do
  adapter_count=$((adapter_count + 1))
  [[ "$mode" == "implicit" ]] || continue
  implicit_count=$((implicit_count + 1))
  printf -- '- %s: %s (file: %s/%s/SKILL.md)\n' "$name" "$description" "$OUT_DIR" "$name" >>"$absolute_catalog"
  printf -- '- %s: %s (file: r0/%s/SKILL.md)\n' "$name" "$description" "$name" >>"$alias_catalog"
done <"$MANIFEST"

absolute_chars="$(wc -m <"$absolute_catalog" | tr -d ' ')"
alias_chars="$(wc -m <"$alias_catalog" | tr -d ' ')"
better_chars="$absolute_chars"
better_form="absolute"
if [[ "$alias_chars" -lt "$absolute_chars" ]]; then
  better_chars="$alias_chars"
  better_form="root-alias"
fi

echo "    manifest adapters: $adapter_count"
echo "    implicit adapters: $implicit_count"
echo "    implicit catalog characters (absolute paths): $absolute_chars"
echo "    implicit catalog characters (root alias r0): $alias_chars"
echo "    better catalog form: $better_form ($better_chars / $BUDGET_LIMIT)"

if [[ "$better_chars" -gt "$BUDGET_LIMIT" ]]; then
  echo "ERROR: implicit EVC catalog exceeds the $BUDGET_LIMIT-character budget" >&2
  exit 1
fi

echo "    clean"
