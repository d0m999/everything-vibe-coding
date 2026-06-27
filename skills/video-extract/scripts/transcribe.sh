#!/usr/bin/env bash
# transcribe.sh <audiofile> <outdir> [model] [language]
# Whisper transcription. model: tiny|base|small|medium|large (small = balanced default).
set -uo pipefail
AUDIO="${1:?usage: transcribe.sh <audiofile> <outdir> [model] [language]}"
OUT="${2:?usage: transcribe.sh <audiofile> <outdir> [model] [language]}"
MODEL="${3:-small}"
WLANG="${4:-}"   # NOT "LANG" — that is the shell locale env var; clobbering it breaks whisper's UTF-8 output
mkdir -p "$OUT"
[ -f "$AUDIO" ] || { echo "ERR: no audio file at $AUDIO"; exit 1; }

# --output_format is single-value (default "all"); passing it twice keeps only the last. Use "all" for txt+srt.
ARGS=(--model "$MODEL" --output_dir "$OUT" --output_format all --verbose False)
[ -n "$WLANG" ] && ARGS+=(--language "$WLANG")

echo "=== whisper ($MODEL) on $AUDIO ==="
whisper "$AUDIO" "${ARGS[@]}" 2>&1 | tail -6
echo "--- output ---"
ls -lh "$OUT"/*.txt "$OUT"/*.srt 2>/dev/null
