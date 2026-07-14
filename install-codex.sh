#!/usr/bin/env bash
# install-codex.sh - symlink this repo's skills and commands into Codex.
#
# Usage:
#   ./install-codex.sh                   # dry-run
#   ./install-codex.sh --apply           # create symlinks
#   ./install-codex.sh --apply --backup  # backup ~/.codex before installing
#   ./install-codex.sh --apply --force   # replace conflicting targets
#   ./install-codex.sh --apply --prune   # also remove dangling symlinks into this repo
#
# Layout:
#   skills/<name>/ -> $CODEX_HOME/skills/<name>/  (defaults to ~/.codex/skills)
#   commands/<name>.md -> $CODEX_HOME/prompts/<name>.md
#   commands/local/<name>.md -> $CODEX_HOME/prompts/<name>.md
#   commands/local/<name>/ -> $CODEX_HOME/prompts/<name>/  (support files)
#   .agents/skills/evc-command-<name>/ -> $CODEX_HOME/skills/evc-command-<name>/
#
# Codex discovers skills from $CODEX_HOME/skills and deprecated custom prompt
# slash commands from $CODEX_HOME/prompts. Installed command names appear as
# skills named <name>; custom prompts, when supported, appear as /prompts:<name>.
#
# Prune (--prune):
#   - Detection always runs once --prune is passed, in both dry-run and --apply.
#   - Scans $CODEX_SKILLS_HOME and $CODEX_PROMPTS_HOME one level deep for symlinks
#     whose target starts with this repo's path but no longer exists on disk.
#   - Never touches non-symlinks or symlinks pointing outside this repo.
#     Deletion itself still requires --apply.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_SKILLS_HOME="$CODEX_HOME/skills"
CODEX_PROMPTS_HOME="$CODEX_HOME/prompts"
TS="$(date +%Y%m%d-%H%M%S)"

MODE="dry-run"
FORCE=false
BACKUP=false
PRUNE=false
for arg in "$@"; do
  case "$arg" in
    --apply) MODE="apply" ;;
    --dry-run) MODE="dry-run" ;;
    --force) FORCE=true ;;
    --backup) BACKUP=true ;;
    --prune) PRUNE=true ;;
    -h|--help)
      sed -n '2,27p' "$0"
      exit 0 ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1 ;;
  esac
done

LINKED=0
ALREADY_OK=0
BACKED_UP=0
SKIPPED_MISSING=0

link_one() {
  local src="$1"
  local dst="$2"
  local required_path="$3"
  local missing_label="$4"
  local rel_src="${src#$REPO_ROOT/}"
  local rel_dst="${dst#$CODEX_HOME/}"

  if [[ ! -e "$required_path" ]]; then
    printf '  %-14s repo/%s\n' "$missing_label" "${required_path#$REPO_ROOT/}"
    SKIPPED_MISSING=$((SKIPPED_MISSING + 1))
    return
  fi

  if [[ -L "$dst" ]]; then
    local current
    current="$(readlink "$dst")"
    if [[ "$current" == "$src" ]]; then
      printf '  ALREADY        ~/.codex/%s -> repo/%s\n' "$rel_dst" "$rel_src"
      ALREADY_OK=$((ALREADY_OK + 1))
      return
    fi
  fi

  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ "$FORCE" == "true" ]]; then
      if [[ "$MODE" == "apply" ]]; then
        rm -rf "$dst"
      fi
      printf '  FORCE-OVER     ~/.codex/%s\n' "$rel_dst"
    else
      local bak="${dst}.bak.${TS}"
      if [[ "$MODE" == "apply" ]]; then
        mv "$dst" "$bak"
      fi
      printf '  BACKUP         ~/.codex/%s -> %s\n' "$rel_dst" "${bak#$CODEX_HOME/}"
      BACKED_UP=$((BACKED_UP + 1))
    fi
  fi

  if [[ "$MODE" == "apply" ]]; then
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
  fi
  printf '  LINK           ~/.codex/%s -> repo/%s\n' "$rel_dst" "$rel_src"
  LINKED=$((LINKED + 1))
}

echo "==> install-codex.sh"
echo "    REPO_ROOT:        $REPO_ROOT"
echo "    CODEX_HOME:       $CODEX_HOME"
echo "    CODEX_SKILLS:     $CODEX_SKILLS_HOME"
echo "    CODEX_PROMPTS:    $CODEX_PROMPTS_HOME"
echo "    MODE:             $MODE"
echo "    FORCE:            $FORCE"
echo "    BACKUP:           $BACKUP"
echo

for d in skills commands; do
  if [[ ! -d "$REPO_ROOT/$d" ]]; then
    echo "ERROR: missing $REPO_ROOT/$d" >&2
    exit 1
  fi
done

if [[ "$BACKUP" == "true" ]]; then
  codex_bak="$HOME/.codex.bak-$TS"
  echo "==> Full backup: $CODEX_HOME -> $codex_bak"
  if [[ "$MODE" == "apply" ]]; then
    if [[ -d "$CODEX_HOME" ]]; then
      cp -R "$CODEX_HOME" "$codex_bak"
      echo "    done"
    else
      echo "    skipped; $CODEX_HOME does not exist yet"
    fi
  else
    echo "    dry-run; would run: cp -R \"$CODEX_HOME\" \"$codex_bak\""
  fi
  echo
fi

if [[ "$MODE" == "apply" ]]; then
  mkdir -p "$CODEX_SKILLS_HOME" "$CODEX_PROMPTS_HOME"
fi

echo "==> Generate Codex command skill wrappers"
if [[ "$MODE" == "apply" ]]; then
  "$REPO_ROOT/scripts/generate-codex-command-skills.sh"
else
  echo "    dry-run; would run scripts/generate-codex-command-skills.sh"
fi
echo

echo "## skills/"
skill_count=0
for d in "$REPO_ROOT/skills"/*/; do
  [[ -d "$d" ]] || continue
  name="$(basename "$d")"
  link_one "${d%/}" "$CODEX_SKILLS_HOME/$name" "${d%/}/SKILL.md" "MISSING-SKILL"
  skill_count=$((skill_count + 1))
done
echo "    (count: $skill_count)"
echo

echo "## prompts/ (from commands/*.md)"
prompt_count=0
for f in "$REPO_ROOT/commands"/*.md; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f")"
  link_one "$f" "$CODEX_PROMPTS_HOME/$name" "$f" "MISSING-PROMPT"
  prompt_count=$((prompt_count + 1))
done
echo "    (count: $prompt_count)"
echo

echo "## prompts/ (from commands/local/)"
local_prompt_count=0
if [[ -d "$REPO_ROOT/commands/local" ]]; then
  for f in "$REPO_ROOT/commands/local"/*.md; do
    [[ -e "$f" ]] || continue
    name="$(basename "$f")"
    link_one "$f" "$CODEX_PROMPTS_HOME/$name" "$f" "MISSING-PROMPT"
    local_prompt_count=$((local_prompt_count + 1))
  done

  for d in "$REPO_ROOT/commands/local"/*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    link_one "${d%/}" "$CODEX_PROMPTS_HOME/$name" "${d%/}" "MISSING-RESOURCE"
    local_prompt_count=$((local_prompt_count + 1))
  done
fi
echo "    (count: $local_prompt_count)"
echo

echo "## command skills/ (from .agents/skills/evc-command-*)"
command_skill_count=0
if [[ -d "$REPO_ROOT/.agents/skills" ]]; then
  for d in "$REPO_ROOT/.agents/skills"/evc-command-*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    link_one "${d%/}" "$CODEX_SKILLS_HOME/$name" "${d%/}/SKILL.md" "MISSING-SKILL"
    command_skill_count=$((command_skill_count + 1))
  done
elif [[ "$MODE" == "dry-run" ]]; then
  echo "    dry-run; wrappers may not exist until --apply runs"
fi
echo "    (count: $command_skill_count)"
echo

PRUNE_CANDIDATES=0
PRUNED=0
if [[ "$PRUNE" == "true" ]]; then
  echo "## prune (dangling symlinks under \$CODEX_HOME pointing into this repo)"
  for subdir in "$CODEX_SKILLS_HOME" "$CODEX_PROMPTS_HOME"; do
    [[ -d "$subdir" ]] || continue
    while IFS= read -r -d '' link; do
      target="$(readlink "$link")"
      [[ "$target" == "$REPO_ROOT/"* ]] || continue
      [[ -e "$target" ]] && continue
      rel_link="${link#$CODEX_HOME/}"
      PRUNE_CANDIDATES=$((PRUNE_CANDIDATES + 1))
      if [[ "$MODE" == "apply" ]]; then
        rm "$link"
        printf '  PRUNED               ~/.codex/%s  (dead -> repo/%s)\n' "$rel_link" "${target#$REPO_ROOT/}"
        PRUNED=$((PRUNED + 1))
      else
        printf '  PRUNE (would remove) ~/.codex/%s  (dead -> repo/%s)\n' "$rel_link" "${target#$REPO_ROOT/}"
      fi
    done < <(find "$subdir" -maxdepth 1 -type l -print0 2>/dev/null)
  done
  echo "    (candidates: $PRUNE_CANDIDATES, removed: $PRUNED)"
  echo
fi

echo "==> Summary"
echo "    Items linked (would link):  $LINKED"
echo "    Already symlinked (no-op):  $ALREADY_OK"
echo "    Conflicts backed up:        $BACKED_UP"
echo "    Missing items skipped:      $SKIPPED_MISSING"
if [[ "$PRUNE" == "true" ]]; then
  echo "    Dangling links pruned:      $PRUNED (candidates: $PRUNE_CANDIDATES)"
fi
echo
if [[ "$MODE" == "dry-run" ]]; then
  echo "    dry-run only; rerun with --apply to install"
else
  echo "    Restart Codex to pick up newly installed skills and prompts."
fi
