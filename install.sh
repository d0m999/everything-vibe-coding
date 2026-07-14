#!/usr/bin/env bash
# install.sh — symlink this repo's items into ~/.claude/
#
# Usage:
#   ./install.sh                # dry-run (preview only)
#   ./install.sh --apply        # actually create symlinks
#   ./install.sh --apply --backup       # backup ~/.claude/ first (recommended)
#   ./install.sh --apply --force        # overwrite existing targets without .bak
#   ./install.sh --apply --backup --force  # both
#
# Layout:
#   agents/*.md           → ~/.claude/agents/<name>.md
#   skills/<name>/        → ~/.claude/skills/<name>/    (directory symlink)
#   commands/*.md         → ~/.claude/commands/<name>.md
#   commands/local/ralph-init.md → ~/.claude/commands/ralph-init.md
#   commands/local/ralph-init/   → ~/.claude/commands/ralph-init/   (directory symlink)
#   hooks/*.js            → ~/.claude/hooks/<name>.js
#
# Skipped:
#   - attic/   (intentional)
#   - any pre-existing gstack* in ~/.claude/  (independent install)
#   - hooks/README.md and anything else in hooks/ that is not *.js
#
# Conflict handling:
#   - Existing path that is NOT a symlink to our repo target → backup to <path>.bak.<ts> (unless --force)
#   - Existing path that already points at our repo target → no-op (idempotent)
#
# Hooks/settings:
#   - This script symlinks the hook SCRIPTS but never writes settings.json.
#     A symlinked script does nothing until it is registered as a hook.
#     Registration snippet: hooks/README.md

set -uo pipefail   # no -e: some checks return non-zero by design

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="$HOME/.claude"
TS="$(date +%Y%m%d-%H%M%S)"

# ===== Flags =====
MODE="dry-run"
FORCE=false
BACKUP=false
for arg in "$@"; do
  case "$arg" in
    --apply)    MODE="apply" ;;
    --dry-run)  MODE="dry-run" ;;
    --force)    FORCE=true ;;
    --backup)   BACKUP=true ;;
    -h|--help)
      sed -n '2,31p' "$0"
      exit 0 ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1 ;;
  esac
done

# ===== Counters =====
LINKED=0
ALREADY_OK=0
BACKED_UP=0
SKIPPED_CONFLICT=0

# ===== Helpers =====
link_one() {
  local src="$1"   # absolute path under $REPO_ROOT
  local dst="$2"   # absolute path under $CLAUDE_HOME
  local rel_src="${src#$REPO_ROOT/}"
  local rel_dst="${dst#$CLAUDE_HOME/}"

  if [[ ! -e "$src" ]]; then
    printf '  ✗ MISSING-SRC  %s\n' "$rel_src"
    return
  fi

  # Already a symlink pointing at our src → no-op
  if [[ -L "$dst" ]]; then
    local current
    current="$(readlink "$dst")"
    if [[ "$current" == "$src" ]]; then
      printf '  ⊙ ALREADY      ~/.claude/%s → repo/%s\n' "$rel_dst" "$rel_src"
      ALREADY_OK=$((ALREADY_OK + 1))
      return
    fi
  fi

  # Conflict: existing different target
  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ "$FORCE" == "true" ]]; then
      if [[ "$MODE" == "apply" ]]; then
        rm -rf "$dst"
      fi
      printf '  ⚠ FORCE-OVER   ~/.claude/%s  (existing removed)\n' "$rel_dst"
    else
      local bak="${dst}.bak.${TS}"
      if [[ "$MODE" == "apply" ]]; then
        mv "$dst" "$bak"
      fi
      printf '  ↻ BACKUP       ~/.claude/%s → %s\n' "$rel_dst" "${bak#$CLAUDE_HOME/}"
      BACKED_UP=$((BACKED_UP + 1))
    fi
  fi

  if [[ "$MODE" == "apply" ]]; then
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
  fi
  printf '  → LINK         ~/.claude/%s → repo/%s\n' "$rel_dst" "$rel_src"
  LINKED=$((LINKED + 1))
}

# ===== Pre-flight =====
echo "==> install.sh"
echo "    REPO_ROOT:    $REPO_ROOT"
echo "    CLAUDE_HOME:  $CLAUDE_HOME"
echo "    MODE:         $MODE"
echo "    FORCE:        $FORCE"
echo "    BACKUP:       $BACKUP"
echo

# Sanity: repo must have what install expects
for d in agents skills commands hooks; do
  if [[ ! -d "$REPO_ROOT/$d" ]]; then
    echo "ERROR: missing $REPO_ROOT/$d" >&2
    exit 1
  fi
done

if [[ ! -d "$CLAUDE_HOME" ]]; then
  echo "ERROR: $CLAUDE_HOME does not exist (Claude Code not installed?)" >&2
  exit 1
fi

# ===== Full ~/.claude backup =====
if [[ "$BACKUP" == "true" ]]; then
  local_bak="$HOME/.claude.bak-$TS"
  echo "==> Full backup: $CLAUDE_HOME → $local_bak"
  if [[ "$MODE" == "apply" ]]; then
    cp -R "$CLAUDE_HOME" "$local_bak"
    echo "    ✓ done"
  else
    echo "    (dry-run; would run: cp -R \"$CLAUDE_HOME\" \"$local_bak\")"
  fi
  echo
fi

# ===== Ensure target subdirs =====
if [[ "$MODE" == "apply" ]]; then
  mkdir -p "$CLAUDE_HOME/agents" "$CLAUDE_HOME/skills" "$CLAUDE_HOME/commands" "$CLAUDE_HOME/hooks"
fi

# ===== agents/ =====
echo "## agents/"
agent_count=0
for f in "$REPO_ROOT/agents"/*.md; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f")"
  link_one "$f" "$CLAUDE_HOME/agents/$name"
  agent_count=$((agent_count + 1))
done
echo "    (count: $agent_count)"
echo

# ===== skills/ =====
echo "## skills/"
skill_count=0
for d in "$REPO_ROOT/skills"/*/; do
  [[ -d "$d" ]] || continue
  name="$(basename "$d")"
  link_one "${d%/}" "$CLAUDE_HOME/skills/$name"
  skill_count=$((skill_count + 1))
done
echo "    (count: $skill_count)"
echo

# ===== commands/ (top-level .md, excluding commands/local/) =====
echo "## commands/ (top-level .md)"
cmd_count=0
for f in "$REPO_ROOT/commands"/*.md; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f")"
  link_one "$f" "$CLAUDE_HOME/commands/$name"
  cmd_count=$((cmd_count + 1))
done
echo "    (count: $cmd_count)"
echo

# ===== commands/local/ (originals — ralph-init etc.) =====
echo "## commands/local/  (originals)"
local_count=0
if [[ -d "$REPO_ROOT/commands/local" ]]; then
  # .md files
  for f in "$REPO_ROOT/commands/local"/*.md; do
    [[ -e "$f" ]] || continue
    name="$(basename "$f")"
    link_one "$f" "$CLAUDE_HOME/commands/$name"
    local_count=$((local_count + 1))
  done
  # subdirectories (e.g. ralph-init/)
  for d in "$REPO_ROOT/commands/local"/*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    link_one "${d%/}" "$CLAUDE_HOME/commands/$name"
    local_count=$((local_count + 1))
  done
fi
echo "    (count: $local_count)"
echo

# ===== hooks/ (scripts only — settings.json registration stays manual) =====
echo "## hooks/ (*.js)"
hook_count=0
for f in "$REPO_ROOT/hooks"/*.js; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f")"
  link_one "$f" "$CLAUDE_HOME/hooks/$name"
  hook_count=$((hook_count + 1))
done
echo "    (count: $hook_count)"
if [[ "$hook_count" -gt 0 ]]; then
  echo "    NOTE: linked scripts are inert until registered in settings.json — see hooks/README.md"
fi
echo

# ===== Summary =====
echo "==> Summary"
echo "    Items linked (would link):  $LINKED"
echo "    Already symlinked (no-op):  $ALREADY_OK"
echo "    Conflicts backed up:        $BACKED_UP"
echo
if [[ "$MODE" == "dry-run" ]]; then
  echo "    (dry-run — no changes made; rerun with --apply to install)"
  echo
  echo "    Recommended first install: ./install.sh --apply --backup"
fi
