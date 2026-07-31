#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GENERATOR="$REPO_ROOT/scripts/generate-codex-skills.sh"
CHECKER="$REPO_ROOT/scripts/check-codex-skills.sh"
INSTALLER="$REPO_ROOT/install-codex.sh"

tmp_root="$(mktemp -d "${TMPDIR:-/tmp}/evc-codex-tests.XXXXXX")"
trap 'rm -rf "$tmp_root"' EXIT

passes=0

pass() {
  echo "  ✓ $1"
  passes=$((passes + 1))
}

fail() {
  echo "  ✗ $1" >&2
  exit 1
}

make_skill() {
  local repo="$1"
  local name="$2"
  mkdir -p "$repo/skills/$name"
  printf -- '---\nname: %s\ndescription: Canonical %s workflow.\n---\n\n# %s\n' \
    "$name" "$name" "$name" >"$repo/skills/$name/SKILL.md"
}

run_generator() {
  local repo="$1"
  local manifest="$2"
  local out="$3"
  EVC_CODEX_REPO_ROOT="$repo" \
  EVC_CODEX_MANIFEST="$manifest" \
  EVC_CODEX_ADAPTER_OUT="$out" \
    "$GENERATOR"
}

expect_generator_failure() {
  local label="$1"
  local repo="$2"
  local manifest="$3"
  local expected="$4"
  local log="$tmp_root/failure.log"
  if run_generator "$repo" "$manifest" "$tmp_root/invalid-out" >"$log" 2>&1; then
    fail "$label: generator unexpectedly succeeded"
  fi
  grep -qF "$expected" "$log" || {
    sed 's/^/      /' "$log" >&2
    fail "$label: expected error '$expected'"
  }
  pass "$label"
}

fixture_repo="$tmp_root/repo"
mkdir -p "$fixture_repo"
for name in a b c d; do
  make_skill "$fixture_repo" "$name"
done
base_manifest="$fixture_repo/codex-skills.tsv"
printf 'a\timplicit\tImplicit adapter A.\nb\texplicit\tExplicit adapter B.\nc\texplicit\tExplicit adapter C.\nd\texplicit\tExplicit adapter D.\n' >"$base_manifest"

missing_manifest="$tmp_root/missing.tsv"
printf 'a\timplicit\tImplicit adapter A.\nb\texplicit\tExplicit adapter B.\nc\texplicit\tExplicit adapter C.\n' >"$missing_manifest"
expect_generator_failure "manifest missing canonical skill fails closed" "$fixture_repo" "$missing_manifest" "not one-to-one"

extra_manifest="$tmp_root/extra.tsv"
cp "$base_manifest" "$extra_manifest"
printf 'extra\texplicit\tUnexpected entry.\n' >>"$extra_manifest"
expect_generator_failure "manifest extra skill fails closed" "$fixture_repo" "$extra_manifest" "has no skills/extra/SKILL.md"

duplicate_manifest="$tmp_root/duplicate.tsv"
printf 'a\timplicit\tImplicit adapter A.\na\texplicit\tDuplicate adapter A.\nb\texplicit\tExplicit adapter B.\nc\texplicit\tExplicit adapter C.\nd\texplicit\tExplicit adapter D.\n' >"$duplicate_manifest"
expect_generator_failure "manifest duplicate name fails closed" "$fixture_repo" "$duplicate_manifest" "duplicate names"

mode_manifest="$tmp_root/mode.tsv"
sed $'s/a\timplicit/a\tautomatic/' "$base_manifest" >"$mode_manifest"
expect_generator_failure "manifest illegal mode fails closed" "$fixture_repo" "$mode_manifest" "invalid mode 'automatic'"

long_description="$(awk 'BEGIN { for (i=0; i<221; i++) printf "x" }')"
long_manifest="$tmp_root/long.tsv"
printf 'a\texplicit\t%s\nb\texplicit\tExplicit adapter B.\nc\texplicit\tExplicit adapter C.\nd\texplicit\tExplicit adapter D.\n' "$long_description" >"$long_manifest"
expect_generator_failure "manifest 220-character limit fails closed" "$fixture_repo" "$long_manifest" "exceeds 220 characters"

implicit_description="$(awk 'BEGIN { for (i=0; i<161; i++) printf "y" }')"
implicit_manifest="$tmp_root/implicit-long.tsv"
printf 'a\timplicit\t%s\nb\texplicit\tExplicit adapter B.\nc\texplicit\tExplicit adapter C.\nd\texplicit\tExplicit adapter D.\n' "$implicit_description" >"$implicit_manifest"
expect_generator_failure "manifest implicit 160-character limit fails closed" "$fixture_repo" "$implicit_manifest" "exceeds 160 characters"

field_manifest="$tmp_root/field.tsv"
printf 'a\timplicit\tImplicit adapter A.\textra\nb\texplicit\tExplicit adapter B.\nc\texplicit\tExplicit adapter C.\nd\texplicit\tExplicit adapter D.\n' >"$field_manifest"
expect_generator_failure "manifest tab in description fails closed" "$fixture_repo" "$field_manifest" "expected exactly 3"

out_dir="$tmp_root/generated"
run_generator "$fixture_repo" "$base_manifest" "$out_dir" >/dev/null
cp -R "$out_dir" "$tmp_root/first-generation"
run_generator "$fixture_repo" "$base_manifest" "$out_dir" >/dev/null
diff -ru "$tmp_root/first-generation" "$out_dir" >/dev/null || fail "generator output changed on second run"
pass "generator is deterministic across consecutive runs"

mkdir -p "$out_dir/stale"
printf 'stale\n' >"$out_dir/stale/SKILL.md"
run_generator "$fixture_repo" "$base_manifest" "$out_dir" >/dev/null
[[ ! -e "$out_dir/stale" ]] || fail "generator did not remove stale output"
pass "generator removes stale generated output"

adapter_count="$(find "$out_dir" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')"
[[ "$adapter_count" == "4" ]] || fail "expected one adapter per canonical skill, got $adapter_count"
grep -qF 'allow_implicit_invocation: true' "$out_dir/a/agents/openai.yaml" || fail "implicit policy missing"
for name in b c d; do
  grep -qF 'allow_implicit_invocation: false' "$out_dir/$name/agents/openai.yaml" || fail "explicit policy missing for $name"
done
grep -qF '../../../skills/a/SKILL.md' "$out_dir/a/SKILL.md" || fail "canonical source path missing"
grep -qF 'from `../../../skills/a/`' "$out_dir/a/SKILL.md" || fail "canonical relative-reference rule missing"
pass "one adapter is emitted per skill with correct policy and canonical source"

EVC_CODEX_REPO_ROOT="$fixture_repo" \
EVC_CODEX_MANIFEST="$base_manifest" \
EVC_CODEX_ADAPTER_OUT="$out_dir" \
  "$CHECKER" >/dev/null
pass "consistency checker accepts exact generated output"

printf '\nlocal drift\n' >>"$out_dir/a/SKILL.md"
if EVC_CODEX_REPO_ROOT="$fixture_repo" \
  EVC_CODEX_MANIFEST="$base_manifest" \
  EVC_CODEX_ADAPTER_OUT="$out_dir" \
  "$CHECKER" >"$tmp_root/drift.log" 2>&1; then
  fail "consistency checker accepted adapter drift"
fi
grep -qF 'adapters have drifted' "$tmp_root/drift.log" || fail "adapter drift error was not explicit"
pass "consistency checker rejects adapter drift"
run_generator "$fixture_repo" "$base_manifest" "$out_dir" >/dev/null

budget_repo="$tmp_root/budget-repo"
budget_manifest="$budget_repo/codex-skills.tsv"
mkdir -p "$budget_repo"
: >"$budget_manifest"
budget_description="$(awk 'BEGIN { for (i=0; i<150; i++) printf "z" }')"
index=0
while [[ "$index" -lt 40 ]]; do
  name="skill-$index"
  make_skill "$budget_repo" "$name"
  printf '%s\timplicit\t%s\n' "$name" "$budget_description" >>"$budget_manifest"
  index=$((index + 1))
done
LC_ALL=C sort -o "$budget_manifest" "$budget_manifest"
budget_out="$budget_repo/.agents/skills"
run_generator "$budget_repo" "$budget_manifest" "$budget_out" >/dev/null
if EVC_CODEX_REPO_ROOT="$budget_repo" \
  EVC_CODEX_MANIFEST="$budget_manifest" \
  EVC_CODEX_ADAPTER_OUT="$budget_out" \
  "$CHECKER" >"$tmp_root/budget.log" 2>&1; then
  fail "budget checker accepted an oversized implicit catalog"
fi
grep -qF 'exceeds the 5000-character budget' "$tmp_root/budget.log" || fail "budget failure was not explicit"
pass "implicit catalog budget fails closed"

codex_home="$tmp_root/codex-home"
external_root="$tmp_root/external"
mkdir -p "$codex_home/skills" "$codex_home/prompts" "$external_root/b" "$external_root/outsider" "$fixture_repo/retired" "$fixture_repo/old-prompt"
ln -s "$fixture_repo/skills/a" "$codex_home/skills/a"
ln -s "$external_root/b" "$codex_home/skills/b"
printf 'preserve c\n' >"$codex_home/skills/c"
ln -s "$fixture_repo/.agents/skills/evc-command-old" "$codex_home/skills/evc-command-old"
ln -s "$fixture_repo/retired" "$codex_home/skills/retired"
ln -s "$external_root/outsider" "$codex_home/skills/outsider"
printf 'foreign\n' >"$codex_home/skills/foreign"
ln -s "$fixture_repo/old-prompt" "$codex_home/prompts/legacy.md"

CODEX_HOME="$codex_home" \
EVC_CODEX_REPO_ROOT="$fixture_repo" \
EVC_CODEX_MANIFEST="$base_manifest" \
EVC_CODEX_ADAPTER_OUT="$fixture_repo/.agents/skills" \
  "$INSTALLER" --dry-run --prune >"$tmp_root/install-dry.log"
grep -qE '^  RELINK[[:space:]]+~/.codex/skills/a ' "$tmp_root/install-dry.log" || fail "dry-run omitted RELINK"
grep -qE '^  LINK[[:space:]]+~/.codex/skills/d ' "$tmp_root/install-dry.log" || fail "dry-run omitted LINK"
grep -qE '^  PRUNE[[:space:]]+~/.codex/skills/evc-command-old ' "$tmp_root/install-dry.log" || fail "dry-run omitted legacy wrapper PRUNE"
grep -qE '^  CONFLICT[[:space:]]+~/.codex/skills/b ' "$tmp_root/install-dry.log" || fail "dry-run omitted symlink CONFLICT"
grep -qE '^  CONFLICT[[:space:]]+~/.codex/skills/c ' "$tmp_root/install-dry.log" || fail "dry-run omitted file CONFLICT"
pass "installer dry-run reports LINK, RELINK, PRUNE, and conflicts"

CODEX_HOME="$codex_home" \
EVC_CODEX_REPO_ROOT="$fixture_repo" \
EVC_CODEX_MANIFEST="$base_manifest" \
EVC_CODEX_ADAPTER_OUT="$fixture_repo/.agents/skills" \
  "$INSTALLER" --apply --prune >"$tmp_root/install-apply.log"
[[ "$(readlink "$codex_home/skills/a")" == "$fixture_repo/.agents/skills/a" ]] || fail "legacy native link was not relinked"
[[ -L "$codex_home/skills/d" ]] || fail "missing adapter was not linked"
[[ ! -L "$codex_home/skills/evc-command-old" ]] || fail "legacy wrapper was not pruned"
[[ ! -L "$codex_home/skills/retired" ]] || fail "retired repo link was not pruned"
[[ ! -L "$codex_home/prompts/legacy.md" ]] || fail "legacy prompt link was not pruned"
[[ "$(readlink "$codex_home/skills/b")" == "$external_root/b" ]] || fail "external symlink conflict was changed"
[[ "$(cat "$codex_home/skills/c")" == "preserve c" ]] || fail "regular-file conflict was changed"
[[ "$(readlink "$codex_home/skills/outsider")" == "$external_root/outsider" ]] || fail "unmanaged external symlink was changed"
[[ "$(cat "$codex_home/skills/foreign")" == "foreign" ]] || fail "unmanaged regular file was changed"
pass "installer migrates repo links and preserves all non-repo content"

echo
echo "Codex adapter regression tests: PASS ($passes checks)"
