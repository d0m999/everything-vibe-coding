#!/usr/bin/env bash
# setup_potoken.sh — idempotently install the bgutil PO-token provider for yt-dlp.
# Needs: pip, git, node, npm. Safe to re-run.
set -uo pipefail
REPO="$HOME/bgutil-ytdlp-pot-provider"
SRV="$REPO/server"

echo "=== install yt-dlp plugin ==="
python3 -m pip install -U bgutil-ytdlp-pot-provider 2>&1 | tail -2

PLUGIN_VER=$(python3 -m pip show bgutil-ytdlp-pot-provider 2>/dev/null | awk '/^Version:/{print $2}')
echo "plugin version: ${PLUGIN_VER:-unknown}"

if [ ! -f "$SRV/build/generate_once.js" ]; then
  echo "=== clone + build generator (matching plugin version) ==="
  URL_REPO="https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git"
  cloned=""
  # Try the plugin version as a tag, with AND without a leading 'v' (repos tag differently),
  # then fall back to the default branch. The old single --branch attempt failed silently on a
  # 'v'-prefix mismatch and then cloned an unrelated default branch with no warning.
  if [ -n "${PLUGIN_VER:-}" ]; then
    for ref in "$PLUGIN_VER" "v$PLUGIN_VER"; do
      rm -rf "$REPO"
      if git clone --depth 1 --branch "$ref" "$URL_REPO" "$REPO" 2>&1 | tail -2; then
        cloned="$ref"; break
      fi
    done
  fi
  if [ -z "$cloned" ]; then
    rm -rf "$REPO"
    git clone --depth 1 "$URL_REPO" "$REPO" 2>&1 | tail -2
    echo "WARN: cloned default branch (no tag matched '${PLUGIN_VER:-<none>}'); generator may not match the installed plugin version"
  else
    echo "cloned generator at tag $cloned"
  fi
  ( cd "$SRV" && npm install 2>&1 | tail -2 && npx tsc 2>&1 | tail -3 )
fi

echo "=== ensure canvas (botguard needs it in server/node_modules) ==="
( cd "$SRV" && node -e "require.resolve('canvas')" 2>/dev/null || npm install canvas 2>&1 | tail -2 )

if [ -f "$SRV/build/generate_once.js" ] && ( cd "$SRV" && node -e "require.resolve('canvas')" 2>/dev/null ); then
  echo "PO_TOKEN_SETUP: ok ($SRV/build/generate_once.js)"
else
  echo "PO_TOKEN_SETUP: FAILED"; exit 1
fi
