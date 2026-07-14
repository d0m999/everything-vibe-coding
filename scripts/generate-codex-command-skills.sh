#!/usr/bin/env bash
# Generate Codex skill wrappers for this repo's Claude Code-style commands.
#
# Codex does not expose these as bare slash commands. A thin skill wrapper makes
# each command discoverable from the Codex skill picker by its command name.
#
# Sources, in order of precedence per name:
#   1. skills/<name>/SKILL.md, for names listed in MIGRATED_COMMAND_SKILLS below.
#      These were gray-rollout-migrated from commands/<name>.md to skills/ on
#      2026-07-14 (Phase 1) and commands/<name>.md was deleted in Phase 2 — the
#      content moved, but Codex still needs an explicit "/name" trigger wrapper
#      since it has no native slash-command concept, so this script keeps
#      generating one, just reading from the new location.
#   2. commands/<name>.md and commands/local/<name>.md — any command not (yet)
#      migrated to skills/.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/.agents/skills"

# Names whose Claude Code command content now lives at skills/<name>/SKILL.md
# instead of commands/<name>.md (2026-07-14 gray-rollout Phase 2 deletion).
MIGRATED_COMMAND_SKILLS=(
  build-fix code-review fastapi-review hookify hookify-configure hookify-help
  hookify-list learn-eval loop-start loop-status mempaw-loop-plan
  mempaw-loop-start mempaw-loop-status model-route plan plan-orchestrate
  plan-prd python-review ralph-init refactor-clean security-scan skill-create
  test-coverage update-codemaps update-docs
)

is_migrated() {
  local name="$1" m
  for m in "${MIGRATED_COMMAND_SKILLS[@]}"; do
    [[ "$m" == "$name" ]] && return 0
  done
  return 1
}

yaml_value() {
  local key="$1"
  local file="$2"
  awk -v key="$key" '
    NR == 1 && $0 == "---" { in_yaml = 1; next }
    in_yaml && $0 == "---" { exit }
    in_yaml && index($0, key ":") == 1 {
      sub("^[^:]+:[[:space:]]*", "")
      gsub(/^"|"$/, "")
      print
      exit
    }
  ' "$file"
}

emit_wrapper() {
  local content_file="$1"
  local name="$2"
  local rel_command
  local desc
  local args
  local wrapper_dir
  local wrapper_file

  rel_command="${content_file#$REPO_ROOT/}"
  desc="$(yaml_value description "$content_file")"
  args="$(yaml_value argument-hint "$content_file")"
  wrapper_dir="$OUT_DIR/evc-command-$name"
  wrapper_file="$wrapper_dir/SKILL.md"

  [[ -n "$desc" ]] || desc="Run the /$name command from everything-vibe-coding."
  [[ -n "$args" ]] || args="optional free-form arguments"

  mkdir -p "$wrapper_dir"
  cat > "$wrapper_file" <<EOF
---
name: $name
description: |
  Run the /$name command from everything-vibe-coding. Use when the user types
  /$name, names \$$name, or asks for this command workflow. Original command
  description: $desc
metadata:
  command-file: $rel_command
  argument-hint: |
    $args
---

# /$name Codex Wrapper

When this skill is invoked, read \`../../../$rel_command\` completely and execute
that command document as the active workflow instruction.

Treat any user text after \`/$name\` or \$$name as \`\$ARGUMENTS\` for the
command document. Resolve relative references from the command file's directory.

This wrapper exists because Codex discovers reusable workflows as skills, while
the source repo stores these workflows as Claude Code-style command files.
EOF
}

mkdir -p "$OUT_DIR"

# Idempotent rebuild: this script only ever emits, so a command removed from commands/
# would otherwise leave its evc-command-<name>/ wrapper behind forever — not a dangling
# symlink (the wrapper dir is real), so no --prune pass can ever catch it.
rm -rf "$OUT_DIR"/evc-command-*/

for f in "$REPO_ROOT/commands"/*.md; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f" .md)"
  is_migrated "$name" && continue
  emit_wrapper "$f" "$name"
done

if [[ -d "$REPO_ROOT/commands/local" ]]; then
  for f in "$REPO_ROOT/commands/local"/*.md; do
    [[ -e "$f" ]] || continue
    name="$(basename "$f" .md)"
    is_migrated "$name" && continue
    emit_wrapper "$f" "$name"
  done
fi

for name in "${MIGRATED_COMMAND_SKILLS[@]}"; do
  skill_file="$REPO_ROOT/skills/$name/SKILL.md"
  if [[ -e "$skill_file" ]]; then
    emit_wrapper "$skill_file" "$name"
  else
    echo "warning: '$name' listed in MIGRATED_COMMAND_SKILLS but $skill_file is missing" >&2
  fi
done
