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
# Manifest = v1 keep: 31 agents + 73 skills + 29 commands (= 133 from ecc).
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
      sed -n '2,14p' "$0"
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
  comment-analyzer        database-reviewer       django-build-resolver
  django-reviewer         doc-updater             docs-lookup
  fastapi-reviewer        harness-optimizer       loop-operator
  mle-reviewer            performance-optimizer   planner
  pr-test-analyzer        python-reviewer         pytorch-build-resolver
  refactor-cleaner        rust-build-resolver     rust-reviewer
  security-reviewer       silent-failure-hunter   swift-build-resolver
  swift-reviewer          tdd-guide               type-design-analyzer
  typescript-reviewer
)

SKILLS=(
  # TS / 前端 (18)
  accessibility               bun-runtime                  design-system
  frontend-design-direction   frontend-patterns            frontend-slides
  liquid-glass-design         make-interfaces-feel-better  motion-advanced
  motion-foundations          motion-patterns              motion-ui
  nestjs-patterns             nextjs-turbopack             nuxt4-patterns
  ui-demo                     ui-to-vue                    vite-patterns
  # Python / AI (14)
  django-celery               django-patterns              django-security
  django-tdd                  django-verification          fal-ai-media
  fastapi-patterns            mle-workflow                 prompt-optimizer
  python-patterns             python-testing               pytorch-patterns
  remotion-video-creation     videodb
  # Agent 工程 (13)
  agent-architecture-audit       agent-eval
  agent-harness-construction     agent-introspection-debugging
  agentic-engineering            agentic-os
  ai-regression-testing          autonomous-agent-harness
  autonomous-loops               continuous-agent-loop
  eval-harness                   ralphinho-rfc-pipeline
  verification-loop
  # 通用工作流 (22)
  api-design                  architecture-decision-records
  canary-watch                clickhouse-io
  codebase-onboarding         coding-standards
  database-migrations         deployment-patterns
  docker-patterns             documentation-lookup
  error-handling              hexagonal-architecture
  hookify-rules
  plankton-code-quality       postgres-patterns
  redis-patterns              repo-scan
  safety-guard                security-bounty-hunter
  security-review             security-scan
  strategic-compact
  # Skill 维护 (3, 归类修正)
  skill-comply                skill-scout                  skill-stocktake
)

COMMANDS=(
  build-fix         code-review        fastapi-review
  hookify           hookify-configure  hookify-help
  hookify-list      learn              learn-eval
  loop-start        loop-status        model-route
  plan              plan-prd           python-review
  refactor-clean    rust-build         rust-review
  rust-test         security-scan      skill-create
  test-coverage     update-codemaps    update-docs
)

# ===== Counters =====
COUNT_COPIED=0
COUNT_SKIPPED=0
COUNT_MISSING=0
COUNT_PLANNED=0

# ===== Functions =====
insert_source_comment() {
  local file="$1"
  local rel="$2"
  local marker="<!-- Source: ecc@${ECC_VERSION}, vendored on ${DATE} from ${rel} -->"

  [[ ! -f "$file" ]] && return

  # idempotent: skip if file already has a Source: ecc@ comment in the first 5 lines
  if head -5 "$file" 2>/dev/null | grep -q "<!-- Source: ecc@"; then
    return
  fi

  local tmp="${file}.tmp.$$"
  { printf '%s\n' "$marker"; cat "$file"; } > "$tmp"
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
    insert_source_comment "$dst" "$rel"
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
echo "    Total in manifest:  $total"
if [[ "$MODE" == "dry-run" ]]; then
  echo "    Would copy:         $COUNT_PLANNED"
fi
echo "    Copied:             $COUNT_COPIED"
echo "    Skipped (exists):   $COUNT_SKIPPED"
echo "    Missing (no src):   $COUNT_MISSING"

if [[ "$MODE" == "dry-run" ]]; then
  echo
  echo "    (dry-run — no changes made; rerun with --apply to copy)"
fi

if [[ "$COUNT_MISSING" -gt 0 ]]; then
  exit 2
fi
