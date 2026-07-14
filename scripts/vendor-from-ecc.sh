#!/usr/bin/env bash
# vendor-from-ecc.sh — copy v1 keep items from ecc plugin into the repo
#
# Usage:
#   scripts/vendor-from-ecc.sh               # dry-run (preview only)
#   scripts/vendor-from-ecc.sh --apply       # actually copy
#   scripts/vendor-from-ecc.sh --apply --force  # overwrite existing targets
#
# Env vars:
#   ECC_ROOT    — ecc plugin root (default: ~/.claude/plugins/marketplaces/ecc)
#   ECC_VERSION — ecc version label (default: read from $ECC_ROOT/VERSION)
#   DATE        — vendoring date (default: today YYYY-MM-DD)
#
# Manifest = v1 keep, excluding everything archived to attic/. Counts are derived from the
# arrays at runtime and printed in the summary — never hardcoded here, so they cannot drift.
# `plan-orchestrate` and `ralph-init` are handled separately (see VENDORING-MANIFEST.md).

set -euo pipefail

# ===== Configuration =====
ECC_ROOT="${ECC_ROOT:-$HOME/.claude/plugins/marketplaces/ecc}"
DATE="${DATE:-$(date +%Y-%m-%d)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ECC_VERSION="${ECC_VERSION:-}"
if [[ -z "$ECC_VERSION" && -f "$ECC_ROOT/VERSION" ]]; then
  ECC_VERSION="$(cat "$ECC_ROOT/VERSION")"
elif [[ -z "$ECC_VERSION" ]]; then
  ECC_VERSION="unknown"
fi

# ===== Flags =====
MODE="dry-run"
FORCE=false
for arg in "$@"; do
  case "$arg" in
    --apply)   MODE="apply" ;;
    --dry-run) MODE="dry-run" ;;
    --force)   FORCE=true ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0 ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1 ;;
  esac
done

# ===== v1 keep manifests =====
AGENTS=(
  a11y-architect          build-error-resolver    code-architect
  code-explorer           code-reviewer           code-simplifier
  comment-analyzer        database-reviewer       doc-updater
  docs-lookup             fastapi-reviewer        harness-optimizer
  loop-operator           mle-reviewer            performance-optimizer
  planner                 pr-test-analyzer        python-reviewer
  pytorch-build-resolver  refactor-cleaner        security-reviewer
  silent-failure-hunter   swift-build-resolver    swift-reviewer
  tdd-guide               type-design-analyzer    typescript-reviewer
)

SKILLS=(
  # TS / 前端 (5)
  accessibility               design-system                frontend-design-direction
  frontend-patterns           make-interfaces-feel-better
  # Swift / iOS (6)
  swiftui-patterns             swift-concurrency-6-2       swift-actor-persistence
  swift-protocol-di-testing    foundation-models-on-device liquid-glass-design
  # Python / AI (6)
  fastapi-patterns            mle-workflow                 prompt-optimizer
  python-patterns             python-testing               pytorch-patterns
  # Agent 工程 (13)
  agent-architecture-audit       agent-eval
  agent-harness-construction     agent-introspection-debugging
  agentic-engineering            agentic-os
  ai-regression-testing          autonomous-agent-harness
  autonomous-loops               continuous-agent-loop
  eval-harness                   ralphinho-rfc-pipeline
  verification-loop
  # 通用工作流 (20)
  api-design                  architecture-decision-records
  canary-watch                codebase-onboarding
  coding-standards            database-migrations
  deployment-patterns         docker-patterns
  documentation-lookup        error-handling
  hexagonal-architecture      hookify-rules
  plankton-code-quality       postgres-patterns
  redis-patterns              repo-scan
  safety-guard                security-review
  security-scan               strategic-compact
  # Skill 维护 (3, 归类修正)
  skill-comply                skill-scout                  skill-stocktake
)

COMMANDS=(
  build-fix         code-review        fastapi-review
  hookify           hookify-configure  hookify-help
  hookify-list      learn              learn-eval
  loop-start        loop-status        model-route
  plan              plan-prd           python-review
  refactor-clean    security-scan      skill-create
  test-coverage     update-codemaps    update-docs
)

# ===== Counters =====
COUNT_COPIED=0
COUNT_SKIPPED=0
COUNT_MISSING=0
COUNT_PLANNED=0
COUNT_ARCHIVED=0

# ===== Functions =====
# Agents get no Source comment at all: the agent loader requires frontmatter
# to start at line 1, and a leading comment silently drops the agent from the
# Available agents list (see commit 887eac6). Skills/commands tolerate — and
# use — a comment placed right after the closing frontmatter `---`.
insert_source_comment() {
  local file="$1"
  local rel="$2"
  local marker="<!-- Source: ecc@${ECC_VERSION}, vendored on ${DATE} from ${rel} -->"

  [[ ! -f "$file" ]] && return

  # idempotent: skip if file already has a Source: ecc@ comment anywhere in the first 10 lines
  if head -10 "$file" 2>/dev/null | grep -q "<!-- Source: ecc@"; then
    return
  fi

  # Only insert when the file has YAML frontmatter starting at line 1;
  # insert after the SECOND `---` line (the closing delimiter), not before the first.
  if [[ "$(sed -n '1p' "$file")" != "---" ]]; then
    return
  fi
  local close_line
  close_line="$(awk 'NR>1 && /^---$/ { print NR; exit }' "$file")"
  [[ -z "$close_line" ]] && return

  local tmp="${file}.tmp.$$"
  awk -v n="$close_line" -v marker="$marker" \
    'NR==n { print; print marker; next } { print }' "$file" > "$tmp"
  mv "$tmp" "$file"
}

copy_one() {
  local type="$1"    # agents | skills | commands
  local name="$2"
  local src dst rel

  if [[ "$type" == "skills" ]]; then
    src="$ECC_ROOT/skills/$name"
    dst="$REPO_ROOT/skills/$name"
    rel="skills/$name"
  else
    src="$ECC_ROOT/$type/$name.md"
    dst="$REPO_ROOT/$type/$name.md"
    rel="$type/$name.md"
  fi

  # attic/ is the record of what v1 deliberately dropped. Vendoring a name that lives
  # there would silently undo that curation and drag its dangling references back in,
  # so refuse rather than copy — even under --force.
  local archived
  if [[ "$type" == "skills" ]]; then
    archived="$REPO_ROOT/attic/skills/$name"
  else
    archived="$REPO_ROOT/attic/$type/$name.md"
  fi
  if [[ -e "$archived" ]]; then
    printf '  ⊘ ARCHIVED %s  (lives in attic/ — refusing; drop it from the manifest)\n' "$rel"
    COUNT_ARCHIVED=$((COUNT_ARCHIVED + 1))
    return
  fi

  if [[ ! -e "$src" ]]; then
    printf '  ✗ MISSING  %s  (no source: %s)\n' "$rel" "$src"
    COUNT_MISSING=$((COUNT_MISSING + 1))
    return
  fi

  if [[ -e "$dst" && "$FORCE" != "true" ]]; then
    printf '  ⊙ SKIPPED  %s  (target exists; use --force to overwrite)\n' "$rel"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    return
  fi

  if [[ "$MODE" == "dry-run" ]]; then
    printf '  → PLAN     %s\n' "$rel"
    COUNT_PLANNED=$((COUNT_PLANNED + 1))
    return
  fi

  # Apply
  mkdir -p "$(dirname "$dst")"
  if [[ "$type" == "skills" ]]; then
    rm -rf "$dst"
    cp -R "$src" "$dst"
    insert_source_comment "$dst/SKILL.md" "$rel/SKILL.md"
  else
    cp "$src" "$dst"
    # Agents get no Source comment — see insert_source_comment's docstring.
    [[ "$type" != "agents" ]] && insert_source_comment "$dst" "$rel"
  fi
  printf '  ✓ COPIED   %s\n' "$rel"
  COUNT_COPIED=$((COUNT_COPIED + 1))
}

# ===== Pre-flight =====
if [[ ! -d "$ECC_ROOT" ]]; then
  echo "ERROR: ECC_ROOT does not exist: $ECC_ROOT" >&2
  exit 1
fi

echo "==> vendor-from-ecc.sh"
echo "    ECC_ROOT:    $ECC_ROOT"
echo "    ECC_VERSION: $ECC_VERSION"
echo "    DATE:        $DATE"
echo "    REPO_ROOT:   $REPO_ROOT"
echo "    MODE:        $MODE"
echo "    FORCE:       $FORCE"
echo

mkdir -p "$REPO_ROOT/agents" "$REPO_ROOT/skills" "$REPO_ROOT/commands"

# ===== Run =====
echo "## Agents (${#AGENTS[@]})"
for n in "${AGENTS[@]}"; do copy_one agents "$n"; done
echo

echo "## Skills (${#SKILLS[@]})"
for n in "${SKILLS[@]}"; do copy_one skills "$n"; done
echo

echo "## Commands (${#COMMANDS[@]})"
for n in "${COMMANDS[@]}"; do copy_one commands "$n"; done
echo

# ===== Summary =====
total=$((${#AGENTS[@]} + ${#SKILLS[@]} + ${#COMMANDS[@]}))
echo "==> Summary"
echo "    Total in manifest:  $total  (${#AGENTS[@]} agents + ${#SKILLS[@]} skills + ${#COMMANDS[@]} commands)"
if [[ "$MODE" == "dry-run" ]]; then
  echo "    Would copy:         $COUNT_PLANNED"
fi
echo "    Copied:             $COUNT_COPIED"
echo "    Skipped (exists):   $COUNT_SKIPPED"
echo "    Missing (no src):   $COUNT_MISSING"
echo "    Archived (refused): $COUNT_ARCHIVED"

if [[ "$MODE" == "dry-run" ]]; then
  echo
  echo "    (dry-run — no changes made; rerun with --apply to copy)"
fi

# A manifest entry that lives in attic/ is a curation regression, not a transient miss:
# fail loudly so it gets pruned instead of quietly resurrecting on the next --apply.
if [[ "$COUNT_ARCHIVED" -gt 0 ]]; then
  echo
  echo "ERROR: $COUNT_ARCHIVED manifest entries are archived in attic/. Remove them from the" >&2
  echo "       AGENTS/SKILLS/COMMANDS arrays above — vendoring them would undo the v1 curation." >&2
  exit 3
fi

if [[ "$COUNT_MISSING" -gt 0 ]]; then
  exit 2
fi
