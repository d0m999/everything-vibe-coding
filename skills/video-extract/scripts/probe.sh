#!/usr/bin/env bash
# probe.sh <url> <workdir>
# Prints video metadata and fetches captions if any.
set -uo pipefail
URL="${1:?usage: probe.sh <url> <workdir>}"
WORK="${2:?usage: probe.sh <url> <workdir>}"
mkdir -p "$WORK"

echo "=== metadata ==="
yt-dlp --skip-download --no-warnings \
  --print "title: %(title)s" \
  --print "duration_s: %(duration)s" \
  --print "uploader: %(uploader)s" \
  --print "upload_date: %(upload_date)s" \
  --print "view_count: %(view_count)s" \
  "$URL" 2>&1 | grep -E "^(title|duration_s|uploader|upload_date|view_count):"

echo "=== captions ==="
# Build the target language list: en + zh + the video's ORIGINAL language (if known).
# A bare ".*" here would pull EVERY available track (often 50+), so resolve the origin
# language explicitly instead. %(language)s renders "NA" when unknown — filter it out.
ORIG_LANG=$(yt-dlp --skip-download --no-warnings --print "%(language)s" "$URL" 2>/dev/null \
  | grep -vE '^(NA|none|null)?$' | head -1)   # no -i: yt-dlp's sentinel is uppercase "NA"; keep real code "na" (Nauru)
SUBLANGS="en.*,zh.*"
[ -n "$ORIG_LANG" ] && { SUBLANGS="$SUBLANGS,${ORIG_LANG}.*"; echo "orig_lang: $ORIG_LANG"; }
SUBS=$(yt-dlp --skip-download --list-subs --no-warnings "$URL" 2>&1)
# Declare "none" ONLY when BOTH manual subs AND auto-captions are absent. The two
# messages are independent: most YouTube videos have auto-captions but no manual subs,
# so an OR here would misreport them as caption-less and skip the cheap transcript path.
if echo "$SUBS" | grep -qi "has no subtitles" && echo "$SUBS" | grep -qi "has no automatic captions"; then
  echo "CAPTIONS: none"
else
  echo "$SUBS" | grep -iE "vtt|srt|json3|^[a-z]{2}(-|\s)" | head -20
  echo "--- fetching captions ($SUBLANGS) ---"
  yt-dlp --skip-download --write-subs --write-auto-subs \
    --sub-langs "$SUBLANGS" --sub-format "vtt/srt/best" \
    -o "$WORK/cap.%(ext)s" --no-warnings "$URL" 2>&1 | grep -iE "writing|destination" | head
  if ls "$WORK"/cap.* 2>/dev/null | grep -q .; then   # any fetched format (vtt/srt/json3/…) counts as a usable transcript source
    echo "CAPTIONS: saved (use these as transcript)"
  else
    echo "CAPTIONS: listed but fetch produced no file — fall back to audio/whisper"
  fi
fi
