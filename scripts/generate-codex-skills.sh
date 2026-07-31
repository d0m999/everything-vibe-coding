#!/usr/bin/env bash
# Generate the complete Codex adapter layer from codex-skills.tsv.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${EVC_CODEX_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
MANIFEST="${EVC_CODEX_MANIFEST:-$REPO_ROOT/codex-skills.tsv}"
OUT_DIR="${EVC_CODEX_ADAPTER_OUT:-$REPO_ROOT/.agents/skills}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ "$OUT_DIR" == /* ]] || fail "adapter output must be an absolute path: $OUT_DIR"
if [[ "$OUT_DIR" == "/" || "$OUT_DIR" == "$REPO_ROOT" || "$OUT_DIR" == "$HOME" ]]; then
  fail "refusing unsafe adapter output path: $OUT_DIR"
fi

yaml_quote() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

validate_manifest() {
  local tmp_dir="$1"
  local names_file="$tmp_dir/manifest-names"
  local canonical_file="$tmp_dir/canonical-names"
  local line_no=0
  local name mode description canonical_name char_count

  [[ -f "$MANIFEST" ]] || fail "manifest not found: $MANIFEST"
  [[ -d "$REPO_ROOT/skills" ]] || fail "canonical skills directory not found: $REPO_ROOT/skills"

  if ! awk -F '\t' 'NF != 3 { printf "line %d has %d fields; expected exactly 3\\n", NR, NF; bad=1 } END { exit bad }' "$MANIFEST" >"$tmp_dir/field-errors"; then
    sed 's/^/ERROR: manifest /' "$tmp_dir/field-errors" >&2
    exit 1
  fi

  : >"$names_file"
  while IFS=$'\t' read -r name mode description; do
    line_no=$((line_no + 1))
    [[ -n "$name" ]] || fail "manifest line $line_no has an empty name"
    [[ "$name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || fail "manifest line $line_no has invalid name '$name'"
    [[ "$mode" == "implicit" || "$mode" == "explicit" ]] || fail "manifest line $line_no has invalid mode '$mode'"
    [[ -n "$description" ]] || fail "manifest line $line_no has an empty description"

    char_count=${#description}
    [[ "$char_count" -le 220 ]] || fail "manifest line $line_no description exceeds 220 characters ($char_count)"
    if [[ "$mode" == "implicit" && "$char_count" -gt 160 ]]; then
      fail "manifest line $line_no implicit description exceeds 160 characters ($char_count)"
    fi

    [[ -f "$REPO_ROOT/skills/$name/SKILL.md" ]] || fail "manifest skill '$name' has no skills/$name/SKILL.md"
    canonical_name="$(awk '
      NR == 1 && $0 == "---" { in_yaml=1; next }
      in_yaml && $0 == "---" { exit }
      in_yaml && /^name:[[:space:]]*/ {
        sub(/^name:[[:space:]]*/, "")
        gsub(/^"|"$/, "")
        print
        exit
      }
    ' "$REPO_ROOT/skills/$name/SKILL.md")"
    [[ "$canonical_name" == "$name" ]] || fail "skills/$name/SKILL.md name '$canonical_name' does not match '$name'"
    printf '%s\n' "$name" >>"$names_file"
  done <"$MANIFEST"

  [[ "$line_no" -gt 0 ]] || fail "manifest is empty"

  if [[ -n "$(LC_ALL=C sort "$names_file" | uniq -d)" ]]; then
    fail "manifest contains duplicate names: $(LC_ALL=C sort "$names_file" | uniq -d | tr '\n' ' ')"
  fi
  if ! LC_ALL=C sort -c "$names_file" 2>/dev/null; then
    fail "manifest names are not sorted"
  fi

  find "$REPO_ROOT/skills" -mindepth 2 -maxdepth 2 -name SKILL.md -print \
    | sed -E 's#^.*/skills/([^/]+)/SKILL\.md$#\1#' \
    | LC_ALL=C sort >"$canonical_file"
  if ! diff -u "$canonical_file" "$names_file" >"$tmp_dir/name-diff"; then
    echo "ERROR: manifest and skills/*/SKILL.md are not one-to-one:" >&2
    cat "$tmp_dir/name-diff" >&2
    exit 1
  fi
}

emit_adapter() {
  local name="$1"
  local mode="$2"
  local description="$3"
  local adapter_dir="$OUT_DIR/$name"
  local implicit=false

  [[ "$mode" == "implicit" ]] && implicit=true
  mkdir -p "$adapter_dir/agents"

  cat >"$adapter_dir/SKILL.md" <<EOF
---
name: $name
description: $(yaml_quote "$description")
---

# $name Codex Adapter

When this skill is invoked, read \`../../../skills/$name/SKILL.md\` completely
before taking any task action.

Treat that canonical file as the active skill instruction. Resolve every relative
file or resource reference from \`../../../skills/$name/\`, not from this adapter
directory.
EOF

  cat >"$adapter_dir/agents/openai.yaml" <<EOF
interface:
  display_name: $(yaml_quote "$name")
  short_description: $(yaml_quote "$description")
  default_prompt: $(yaml_quote "Use \$$name for this task.")
policy:
  allow_implicit_invocation: $implicit
EOF
}

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/evc-codex-generate.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT
validate_manifest "$tmp_dir"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

adapter_count=0
implicit_count=0
while IFS=$'\t' read -r name mode description; do
  emit_adapter "$name" "$mode" "$description"
  adapter_count=$((adapter_count + 1))
  [[ "$mode" == "implicit" ]] && implicit_count=$((implicit_count + 1))
done <"$MANIFEST"

echo "Generated $adapter_count Codex adapters in ${OUT_DIR#$REPO_ROOT/} ($implicit_count implicit)."
