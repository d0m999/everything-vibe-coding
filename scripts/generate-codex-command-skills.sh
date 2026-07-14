#!/usr/bin/env bash
# Generate Codex skill wrappers for this repo's Claude Code-style commands.
#
# Codex does not expose these as bare slash commands. A thin skill wrapper makes
# each command discoverable from the Codex skill picker by its command name.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/.agents/skills"

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
  local command_file="$1"
  local name
  local rel_command
  local desc
  local args
  local wrapper_dir
  local wrapper_file

  name="$(basename "$command_file" .md)"
  rel_command="${command_file#$REPO_ROOT/}"
  desc="$(yaml_value description "$command_file")"
  args="$(yaml_value argument-hint "$command_file")"
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
  emit_wrapper "$f"
done

if [[ -d "$REPO_ROOT/commands/local" ]]; then
  for f in "$REPO_ROOT/commands/local"/*.md; do
    [[ -e "$f" ]] || continue
    emit_wrapper "$f"
  done
fi
