#!/usr/bin/env bash
# Compatibility entrypoint. Codex now uses one adapter per canonical skill.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/generate-codex-skills.sh" "$@"
