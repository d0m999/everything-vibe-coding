#!/usr/bin/env bash
# fast_download.sh <url> <workdir>
# Try yt-dlp with escalating strategies. On success leaves audio.* (+ video.* if possible).
# Exit 0 if audio obtained, else 1 (caller should fall back to the browser path).
set -uo pipefail
URL="${1:?usage: fast_download.sh <url> <workdir>}"
WORK="${2:?usage: fast_download.sh <url> <workdir>}"
mkdir -p "$WORK"
cd "$WORK" || exit 1

# Success = the post-processed FINAL artifact (audio.mp3). A partial source download
# (audio.webm/.m4a, or with --no-part the final name pre-conversion) must NOT count as
# success — otherwise a flaky strategy "succeeds", escalation + browser fallback are
# skipped (SKILL.md: exit 0 = skip browser path), and a truncated fragment reaches whisper.
audio_ok() { ls audio.mp3 2>/dev/null | head -1; }

STRATS=(
  ""
  "--cookies-from-browser chrome --js-runtimes node"
  "--cookies-from-browser chrome --js-runtimes node --extractor-args youtube:player_client=web_safari"
  "--js-runtimes node"  # relies on bgutil PO-token if setup_potoken.sh was run
)

for s in "${STRATS[@]}"; do
  echo "=== audio strategy: ${s:-plain} ==="
  rm -f audio.mp3 audio.m4a audio.webm 2>/dev/null || true   # a prior strategy's partial must not look like success
  yt-dlp $s -f "ba/bestaudio/best" -x --audio-format mp3 --audio-quality 5 \
    -o "audio.%(ext)s" --no-warnings --no-part "$URL" 2>&1 | tail -4
  if [ -n "$(audio_ok)" ]; then echo "AUDIO_OK"; break; fi
done

if [ -z "$(audio_ok)" ]; then
  echo "FAST_DOWNLOAD: FAILED (likely SABR/PO-token) — use browser fallback"; exit 1
fi

# best-effort low-res video for frame extraction (480p), don't fail the script if it can't
echo "=== video (480p, best-effort) ==="
for s in "${STRATS[@]}"; do
  rm -f video.mp4 video.mkv video.webm 2>/dev/null || true
  # NO --no-part here: a partial then stays video.*.part, so the real-container test below
  # correctly rejects it (with --no-part a partial would take the final name and falsely pass).
  yt-dlp $s -f "b[height<=480]/bv*[height<=480]+ba/best[height<=480]/95/94/93" \
    -o "video.%(ext)s" --no-warnings "$URL" 2>&1 | tail -3
  if ls video.mp4 video.mkv video.webm >/dev/null 2>&1; then echo "VIDEO_OK"; break; fi
done

echo "FAST_DOWNLOAD: ok ($(audio_ok))"
exit 0
