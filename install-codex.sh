#!/usr/bin/env bash
# install-codex.sh - reconcile this repo's generated Codex adapters.
#
# Usage:
#   ./install-codex.sh                   # dry-run
#   ./install-codex.sh --apply           # generate and link adapters
#   ./install-codex.sh --apply --backup  # backup CODEX_HOME before installing
#   ./install-codex.sh --apply --force   # explicitly replace conflicts
#   ./install-codex.sh --apply --prune   # migrate old repo links and prune retired ones
#
# Layout:
#   .agents/skills/<name>/ -> $CODEX_HOME/skills/<name>/
#
# Safety:
#   - A same-name symlink into this repo is RELINKed without a pointless backup.
#   - With --prune, repo-owned links outside the manifest are removed.
#   - Non-symlinks and symlinks outside this repo are CONFLICTs and remain untouched
#     unless the caller explicitly passes --force.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${EVC_CODEX_REPO_ROOT:-$SCRIPT_DIR}"
MANIFEST="${EVC_CODEX_MANIFEST:-$REPO_ROOT/codex-skills.tsv}"
ADAPTER_DIR="${EVC_CODEX_ADAPTER_OUT:-$REPO_ROOT/.agents/skills}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_SKILLS_HOME="$CODEX_HOME/skills"
CODEX_PROMPTS_HOME="$CODEX_HOME/prompts"
TS="$(date +%Y%m%d-%H%M%S)"

if [[ "$CODEX_HOME" != /* || "$CODEX_HOME" == "/" ]]; then
  echo "ERROR: CODEX_HOME must be a safe absolute path: $CODEX_HOME" >&2
  exit 1
fi

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
      sed -n '2,18p' "$0"
      exit 0 ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1 ;;
  esac
done

LINKED=0
RELINKED=0
ALREADY_OK=0
CONFLICTS=0
PRUNE_CANDIDATES=0
PRUNED=0

is_repo_target() {
  local target="$1"
  [[ "$target" == "$REPO_ROOT/"* ]]
}

link_adapter() {
  local name="$1"
  local src="$ADAPTER_DIR/$name"
  local dst="$CODEX_SKILLS_HOME/$name"
  local current rel_src rel_dst
  rel_src="${src#$REPO_ROOT/}"
  rel_dst="${dst#$CODEX_HOME/}"

  if [[ -L "$dst" ]]; then
    current="$(readlink "$dst")"
    if [[ "$current" == "$src" ]]; then
      printf '  ALREADY        ~/.codex/%s -> repo/%s\n' "$rel_dst" "$rel_src"
      ALREADY_OK=$((ALREADY_OK + 1))
      return
    fi
    if is_repo_target "$current"; then
      if [[ "$MODE" == "apply" ]]; then
        rm "$dst"
        ln -s "$src" "$dst"
      fi
      printf '  RELINK         ~/.codex/%s  repo/%s -> repo/%s\n' \
        "$rel_dst" "${current#$REPO_ROOT/}" "$rel_src"
      RELINKED=$((RELINKED + 1))
      return
    fi
  fi

  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ "$FORCE" == "true" ]]; then
      if [[ "$MODE" == "apply" ]]; then
        rm -rf "$dst"
        ln -s "$src" "$dst"
      fi
      printf '  FORCE          ~/.codex/%s  (explicitly replacing existing target)\n' "$rel_dst"
      printf '  LINK           ~/.codex/%s -> repo/%s\n' "$rel_dst" "$rel_src"
      LINKED=$((LINKED + 1))
    else
      printf '  CONFLICT       ~/.codex/%s  (preserved; not a repo-owned symlink)\n' "$rel_dst"
      CONFLICTS=$((CONFLICTS + 1))
    fi
    return
  fi

  if [[ "$MODE" == "apply" ]]; then
    [[ -f "$src/SKILL.md" ]] || {
      echo "ERROR: generated adapter missing: $src/SKILL.md" >&2
      exit 1
    }
    mkdir -p "$CODEX_SKILLS_HOME"
    ln -s "$src" "$dst"
  fi
  printf '  LINK           ~/.codex/%s -> repo/%s\n' "$rel_dst" "$rel_src"
  LINKED=$((LINKED + 1))
}

manifest_has_name() {
  local candidate="$1"
  awk -F '\t' -v name="$candidate" '$1 == name { found=1 } END { exit !found }' "$MANIFEST"
}

validation_dir="$(mktemp -d "${TMPDIR:-/tmp}/evc-codex-install.XXXXXX")"
trap 'rm -rf "$validation_dir"' EXIT
if ! EVC_CODEX_REPO_ROOT="$REPO_ROOT" \
  EVC_CODEX_MANIFEST="$MANIFEST" \
  EVC_CODEX_ADAPTER_OUT="$validation_dir/adapters" \
  "$SCRIPT_DIR/scripts/generate-codex-skills.sh" >/dev/null; then
  echo "ERROR: Codex manifest validation failed" >&2
  exit 1
fi

echo "==> install-codex.sh"
echo "    REPO_ROOT:        $REPO_ROOT"
echo "    MANIFEST:         $MANIFEST"
echo "    ADAPTER_DIR:      $ADAPTER_DIR"
echo "    CODEX_HOME:       $CODEX_HOME"
echo "    MODE:             $MODE"
echo "    FORCE:            $FORCE"
echo "    BACKUP:           $BACKUP"
echo "    PRUNE:            $PRUNE"
echo

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
    echo "    dry-run; would copy CODEX_HOME to $codex_bak"
  fi
  echo
fi

if [[ "$MODE" == "apply" ]]; then
  mkdir -p "$CODEX_SKILLS_HOME"
  if ! EVC_CODEX_REPO_ROOT="$REPO_ROOT" \
    EVC_CODEX_MANIFEST="$MANIFEST" \
    EVC_CODEX_ADAPTER_OUT="$ADAPTER_DIR" \
    "$SCRIPT_DIR/scripts/generate-codex-skills.sh"; then
    echo "ERROR: failed to generate Codex adapters" >&2
    exit 1
  fi
fi

echo "## adapters/"
adapter_count=0
while IFS=$'\t' read -r name _mode _description; do
  link_adapter "$name"
  adapter_count=$((adapter_count + 1))
done <"$MANIFEST"
echo "    (count: $adapter_count)"
echo

if [[ "$PRUNE" == "true" ]]; then
  echo "## prune (repo-owned Codex links outside the adapter manifest)"
  for subdir in "$CODEX_SKILLS_HOME" "$CODEX_PROMPTS_HOME"; do
    [[ -d "$subdir" ]] || continue
    while IFS= read -r -d '' link; do
      target="$(readlink "$link")"
      is_repo_target "$target" || continue

      if [[ "$subdir" == "$CODEX_SKILLS_HOME" ]]; then
        link_name="$(basename "$link")"
        if manifest_has_name "$link_name"; then
          continue
        fi
      fi

      rel_link="${link#$CODEX_HOME/}"
      PRUNE_CANDIDATES=$((PRUNE_CANDIDATES + 1))
      if [[ "$MODE" == "apply" ]]; then
        rm "$link"
        PRUNED=$((PRUNED + 1))
        printf '  PRUNE          ~/.codex/%s  (removed repo/%s)\n' "$rel_link" "${target#$REPO_ROOT/}"
      else
        printf '  PRUNE          ~/.codex/%s  (would remove repo/%s)\n' "$rel_link" "${target#$REPO_ROOT/}"
      fi
    done < <(find "$subdir" -maxdepth 1 -type l -print0 2>/dev/null)
  done
  echo "    (candidates: $PRUNE_CANDIDATES, removed: $PRUNED)"
  echo
fi

echo "==> Summary"
echo "    Items linked:              $LINKED"
echo "    Repo links relinked:       $RELINKED"
echo "    Already correct:           $ALREADY_OK"
echo "    Preserved conflicts:       $CONFLICTS"
if [[ "$PRUNE" == "true" ]]; then
  echo "    Repo links pruned:         $PRUNED (candidates: $PRUNE_CANDIDATES)"
fi
echo
if [[ "$MODE" == "dry-run" ]]; then
  echo "    dry-run only; rerun with --apply to reconcile"
else
  echo "    Restart Codex to pick up newly installed adapters."
fi
