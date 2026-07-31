#!/usr/bin/env bash
# doctor.sh — the one deterministic self-check entrypoint for this repo. No LLM, seconds-fast.
#
# Sections 1-6 gate the exit code; section 7 is informational only.
#   1. Skill/agent structure    — skills/*/SKILL.md and agents/*.md are parseable and self-consistent
#   2. Path existence           — scripts/*.{js,sh,py} and docs/*.md paths referenced from skill/command
#                                  bodies actually exist (repo-root or, for skills, the skill's own dir)
#   3. README path consistency  — README's repo-structure tree + backtick paths point to real files
#   4. Codex adapter integrity  — manifest, generated output, policy, canonical paths, catalog budget
#   5. Install-face drift       — delegates to install.sh/install-codex.sh --dry-run --prune
#   6. Hook registration        — read-only check against settings.json + settings.local.json
#   7. Installed footprint      — informational count of repo-owned symlinks
#
# Exit codes: 0 = clean, 1 = one or more of sections 1-6 failed.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FAIL=0

yaml_field() {
  # Prints the trimmed value of a top-level frontmatter key, or nothing if absent/empty.
  # A bare block-scalar indicator (|, >, |-, >- ...) with no inline text counts as present.
  local file="$1" key="$2"
  awk -v key="$key" '
    NR==1 && $0=="---" { inYaml=1; next }
    inYaml && $0=="---" { exit }
    inYaml && $0 ~ ("^" key ":[[:space:]]*") {
      val=$0
      sub("^" key ":[[:space:]]*", "", val)
      gsub(/^"|"$/, "", val)
      if (val ~ /^[|>][+-]?[[:space:]]*$/) { print "<block>"; exit }
      print val
      exit
    }
  ' "$file"
}

# ===== [1/7] Skill / agent structure =====
echo "==> [1/7] Skill / agent structure"
sec1_fail=0
for d in skills/*/; do
  [[ -d "$d" ]] || continue
  name="$(basename "$d")"
  smd="${d}SKILL.md"
  if [[ ! -f "$smd" ]]; then
    echo "  ✗ skills/$name: missing SKILL.md"
    sec1_fail=1
    continue
  fi
  if [[ "$(sed -n '1p' "$smd")" != "---" ]]; then
    echo "  ✗ skills/$name/SKILL.md: does not start with frontmatter (---)"
    sec1_fail=1
    continue
  fi
  fname="$(yaml_field "$smd" name)"
  fdesc="$(yaml_field "$smd" description)"
  [[ -n "$fname" ]] || { echo "  ✗ skills/$name/SKILL.md: empty/missing name:"; sec1_fail=1; }
  [[ -n "$fdesc" ]] || { echo "  ✗ skills/$name/SKILL.md: empty/missing description:"; sec1_fail=1; }
  if [[ -n "$fname" && "$fname" != "$name" ]]; then
    echo "  ✗ skills/$name/SKILL.md: name: ($fname) != directory ($name)"
    sec1_fail=1
  fi
done
# Agents: Claude Code resolves agents by frontmatter name:, not filename — but this repo's
# convention (and every existing agent) keeps them equal, so drift here is worth flagging.
for f in agents/*.md; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f" .md)"
  fname="$(yaml_field "$f" name)"
  [[ -n "$fname" ]] || { echo "  ✗ agents/$base.md: empty/missing name:"; sec1_fail=1; continue; }
  if [[ "$fname" != "$base" ]]; then
    echo "  ✗ agents/$base.md: name: ($fname) != filename ($base)"
    sec1_fail=1
  fi
done
# commands/*.md are intentionally NOT checked for name: — Claude Code resolves commands by
# filename, and name: is not a real field for them; checking it would only produce noise.
if [[ "$sec1_fail" -eq 0 ]]; then
  echo "    clean"
else
  FAIL=1
fi
echo

# ===== [2/7] Path existence =====
echo "==> [2/7] Path existence (scripts/*.{js,sh,py}, docs/*.md referenced in skill/command bodies)"
sec2_fail=0
# Known generic-template mentions: commands/update-docs.md instructs Claude to generate these
# files IN WHATEVER TARGET PROJECT /update-docs runs against — they are not claims that this
# repo itself has them. Mirrors check-references.sh's accepted-false-positive convention
# (see docs/UPSTREAM.md) rather than pretending regex can distinguish intent from syntax.
ALLOW_GENERIC_DOC_REFS="docs/CONTRIBUTING.md docs/RUNBOOK.md"

check_ref() {
  local ref="$1" from_skill_dir="$2"
  [[ -e "$REPO_ROOT/$ref" ]] && return 0
  if [[ -n "$from_skill_dir" && -e "$REPO_ROOT/$from_skill_dir/$ref" ]]; then
    return 0
  fi
  for allowed in $ALLOW_GENERIC_DOC_REFS; do
    [[ "$ref" == "$allowed" ]] && return 0
  done
  return 1
}

for f in skills/*/SKILL.md; do
  [[ -e "$f" ]] || continue
  skill_dir="$(dirname "$f")"
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    if ! check_ref "$ref" "$skill_dir"; then
      echo "  ✗ $f references \`$ref\` — not found (repo root or $skill_dir/)"
      sec2_fail=1
    fi
  done < <(grep -ohE '`(scripts/[A-Za-z0-9_-]+\.(js|sh|py)|docs/[A-Za-z0-9_-]+\.md)`' "$f" | tr -d '`' | sort -u)
done
for f in commands/*.md commands/local/*.md; do
  [[ -e "$f" ]] || continue
  while IFS= read -r ref; do
    [[ -n "$ref" ]] || continue
    if ! check_ref "$ref" ""; then
      echo "  ✗ $f references \`$ref\` — not found"
      sec2_fail=1
    fi
  done < <(grep -ohE '`(scripts/[A-Za-z0-9_-]+\.(js|sh|py)|docs/[A-Za-z0-9_-]+\.md)`' "$f" | tr -d '`' | sort -u)
done
if [[ "$sec2_fail" -eq 0 ]]; then
  echo "    clean"
else
  FAIL=1
fi
echo

# ===== [3/7] README path consistency =====
echo "==> [3/7] README path consistency"
sec3_fail=0
tree_block="$(awk '
  /^## 仓库结构/ { insec=1 }
  insec && /^```$/ { c++; if (c==1) { infence=1; next } else { exit } }
  infence { print }
' README.md)"

readme_nodes="$(awk '
  {
    line=$0
    if (line == ".") next
    if (line ~ /^[│ ]+[├└]── /) {
      rest=line; sub(/^[│ ]*[├└]── /, "", rest); split(rest, a, " ")
      print parent a[1]
    } else if (line ~ /^[├└]── /) {
      rest=line; sub(/^[├└]── /, "", rest); split(rest, a, " ")
      print a[1]
      if (a[1] ~ /\/$/) parent=a[1]
    }
  }
' <<< "$tree_block")"

backtick_refs="$(grep -ohE '`[^`]+`' README.md | tr -d '`')"

is_excluded() {
  case "$1" in
    /*) return 0 ;;           # slash command, e.g. /browse
    \~*) return 0 ;;          # $HOME-relative, e.g. ~/.claude/
    *'*'*) return 0 ;;        # glob, e.g. commands/*.md
    *'<'*|*'>'*) return 0 ;;  # placeholder, e.g. <lang>-reviewer
    *'$'*) return 0 ;;        # shell variable interpolation, e.g. $CODEX_HOME/skills
  esac
  return 1
}

# Tree nodes are checked unconditionally (they're extracted specifically from the repo-structure
# diagram, so by construction every one of them is a path claim). Loose backtick spans anywhere
# in the prose are noisier — a bare word like `manage.py` or `git pull` is a generic example, not
# a repo-path claim — so those are only checked when they contain a "/", the one reliable signal
# that the author meant an actual path rather than a filename mentioned in passing.
all_refs="$(printf '%s\n%s\n' "$readme_nodes" "$backtick_refs" | sort -u)"
while IFS= read -r ref; do
  [[ -n "$ref" ]] || continue
  is_excluded "$ref" && continue
  if ! grep -qxF -- "$ref" <<< "$readme_nodes"; then
    [[ "$ref" == */* ]] || continue
  fi
  [[ -e "$REPO_ROOT/${ref%/}" ]] || { echo "  ✗ README.md references \`$ref\` — not found"; sec3_fail=1; }
done <<< "$all_refs"

if [[ "$sec3_fail" -eq 0 ]]; then
  echo "    clean"
else
  FAIL=1
fi
echo

# ===== [4/7] Codex adapter integrity and context budget =====
echo "==> [4/7] Codex adapter integrity and context budget"
sec4_fail=0
codex_check="$("$REPO_ROOT/scripts/check-codex-skills.sh" 2>&1)"
codex_check_status=$?
if [[ "$codex_check_status" -ne 0 ]]; then
  echo "  ✗ scripts/check-codex-skills.sh exited $codex_check_status — output:"
  echo "$codex_check" | sed 's/^/      /'
  sec4_fail=1
else
  echo "$codex_check"
fi
if [[ "$sec4_fail" -eq 0 ]]; then
  :
else
  FAIL=1
fi
echo

# ===== [5/7] Install-face drift (delegates to install.sh / install-codex.sh) =====
echo "==> [5/7] Install-face drift"
sec5_fail=0

claude_dry="$("$REPO_ROOT/install.sh" --dry-run --prune 2>&1)"
claude_dry_status=$?
if [[ "$claude_dry_status" -ne 0 ]]; then
  echo "  ✗ install.sh --dry-run --prune exited $claude_dry_status (precondition failure, not drift) — output:"
  echo "$claude_dry" | sed 's/^/      /'
  sec5_fail=1
else
  n="$(grep -c '→ LINK' <<< "$claude_dry" || true)"
  if [[ "$n" -gt 0 ]]; then
    echo "  ✗ ~/.claude: $n item(s) in repo but not installed — run ./install.sh --apply"
    sec5_fail=1
  fi
  n="$(grep -c 'PRUNE (would remove)' <<< "$claude_dry" || true)"
  if [[ "$n" -gt 0 ]]; then
    echo "  ✗ ~/.claude: $n dangling symlink(s) into this repo — run ./install.sh --apply --prune"
    sec5_fail=1
  fi
fi

codex_dry="$("$REPO_ROOT/install-codex.sh" --dry-run --prune 2>&1)"
codex_dry_status=$?
if [[ "$codex_dry_status" -ne 0 ]]; then
  echo "  ✗ install-codex.sh --dry-run --prune exited $codex_dry_status (precondition failure, not drift) — output:"
  echo "$codex_dry" | sed 's/^/      /'
  sec5_fail=1
else
  for action in LINK RELINK PRUNE CONFLICT; do
    n="$(grep -cE "^  $action[[:space:]]" <<< "$codex_dry" || true)"
    [[ "$n" -gt 0 ]] || continue
    case "$action" in
      LINK) message="$n adapter(s) not installed" ;;
      RELINK) message="$n repo link(s) need migration" ;;
      PRUNE) message="$n retired repo link(s) need pruning" ;;
      CONFLICT) message="$n preserved conflict(s) block complete installation" ;;
    esac
    echo "  ✗ ~/.codex: $message — run ./install-codex.sh --apply --prune and resolve conflicts explicitly"
    sec5_fail=1
  done
fi

if [[ "$sec5_fail" -eq 0 ]]; then
  echo "    clean"
else
  FAIL=1
fi
echo

# ===== [6/7] Hook registration (read-only) =====
echo "==> [6/7] Hook registration (read-only; never writes settings.json)"
sec6_fail=0
settings_blob=""
for sf in "$HOME/.claude/settings.json" "$HOME/.claude/settings.local.json"; do
  [[ -f "$sf" ]] && settings_blob+="$(cat "$sf")"$'\n'
done
for f in hooks/*.js; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f")"
  if grep -qF "$name" <<< "$settings_blob"; then
    echo "  ⊙ $name registered"
  else
    echo "  ✗ $name not registered in settings.json or settings.local.json"
    sec6_fail=1
  fi
done
if [[ "$sec6_fail" -eq 0 ]]; then
  echo "    clean"
else
  FAIL=1
fi
echo

# ===== [7/7] Installed footprint (informational only — not counted in exit status) =====
echo "==> [7/7] Installed footprint (informational)"
count_owned_symlinks() {
  local dir="$1" n=0
  [[ -d "$dir" ]] || { echo 0; return; }
  while IFS= read -r -d '' link; do
    local t; t="$(readlink "$link")"
    [[ "$t" == "$REPO_ROOT/"* ]] && n=$((n + 1))
  done < <(find "$dir" -maxdepth 1 -type l -print0 2>/dev/null)
  echo "$n"
}
claude_owned=0
for sub in agents skills commands hooks; do
  claude_owned=$((claude_owned + $(count_owned_symlinks "$HOME/.claude/$sub")))
done
codex_owned=0
for sub in skills prompts; do
  codex_owned=$((codex_owned + $(count_owned_symlinks "$HOME/.codex/$sub")))
done
echo "    ~/.claude repo-owned symlinks: $claude_owned"
echo "    ~/.codex  repo-owned symlinks: $codex_owned"
echo

if [[ "$FAIL" -eq 0 ]]; then
  echo "==> doctor.sh: CLEAN"
else
  echo "==> doctor.sh: FAILED (see ✗ lines above)"
fi
exit "$FAIL"
