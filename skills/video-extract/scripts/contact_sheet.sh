#!/usr/bin/env bash
# contact_sheet.sh <framedir> <out.png> [cols] [thumb_w] [per_sheet]
# Tile frames (sorted by name) into contact sheet(s) for quick visual mapping.
# If frames exceed per_sheet, emits out.1.png, out.2.png, ...
# Portable: works on macOS bash 3.2 (no mapfile).
set -uo pipefail
DIR="${1:?usage: contact_sheet.sh <framedir> <out.png> [cols] [thumb_w] [per_sheet]}"
OUT="${2:?usage: contact_sheet.sh <framedir> <out.png> [cols] [thumb_w] [per_sheet]}"
COLS="${3:-4}"
TW="${4:-520}"
PER="${5:-20}"
ROWS=$(( (PER + COLS - 1) / COLS ))

N=$(ls "$DIR"/*.png 2>/dev/null | wc -l | tr -d ' ')
[ "$N" -eq 0 ] && { echo "no frames in $DIR"; exit 1; }

if [ "$N" -le "$PER" ]; then
  ffmpeg -y -pattern_type glob -i "$DIR/*.png" \
    -vf "scale=${TW}:-1,tile=${COLS}x${ROWS}:padding=6:color=0x222222" "$OUT" >/dev/null 2>&1
  echo "sheet: $OUT  (frames sorted by name; pos k = file k)"
else
  tmp=$(mktemp -d); i=0; s=0
  DIRABS=$(cd "$DIR" && pwd)   # absolute so symlinks resolve from $tmp, not relative-to-cwd (dangling)
  for f in $(ls "$DIR"/*.png | sort); do
    sub=$((i / PER)); mkdir -p "$tmp/$sub"
    ln -sf "$DIRABS/$(basename "$f")" "$tmp/$sub/$(printf '%05d' $i)_$(basename "$f")"
    i=$((i+1))
  done
  for d in "$tmp"/*/; do
    s=$((s+1))
    ffmpeg -y -pattern_type glob -i "$d*.png" \
      -vf "scale=${TW}:-1,tile=${COLS}x${ROWS}:padding=6:color=0x222222" "${OUT%.png}.${s}.png" >/dev/null 2>&1
    echo "sheet: ${OUT%.png}.${s}.png"
  done
  rm -rf "$tmp"
fi
echo "frames=$N cols=$COLS per_sheet=$PER"
