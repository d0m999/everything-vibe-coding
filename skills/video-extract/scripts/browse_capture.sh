#!/usr/bin/env bash
# browse_capture.sh <url> <workdir> [start] [end] [step]
# Drive GStack browse: connect (headed), play, and screenshot the <video> element
# every <step> seconds from <start> to <end>. Robust seek via requestVideoFrameCallback.
# Frames land in <workdir>/frames/. Run again with a finer step/window to re-capture slides.
set -uo pipefail
URL="${1:?usage: browse_capture.sh <url> <workdir> [start] [end] [step]}"
WORK="${2:?usage: browse_capture.sh <url> <workdir> [start] [end] [step]}"
START="${3:-0}"
END="${4:-}"
STEP="${5:-50}"
[ "$STEP" -gt 0 ] 2>/dev/null || { echo "ERR: step must be a positive integer (got '$STEP') — a 0/non-numeric step loops forever"; exit 1; }
OUT="$WORK/frames"
mkdir -p "$OUT"

# resolve gstack browse binary
B=""
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
[ -n "$_ROOT" ] && [ -x "$_ROOT/.claude/skills/gstack/browse/dist/browse" ] && B="$_ROOT/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && [ -x "$HOME/.claude/skills/gstack/browse/dist/browse" ] && B="$HOME/.claude/skills/gstack/browse/dist/browse"
if [ -z "$B" ]; then echo "ERR: gstack 'browse' not found. Build it (~/.claude/skills/connect-chrome) or adapt to Playwright MCP."; exit 1; fi

# connect (idempotent-ish): cleanup stale locks, then connect
PROF="$HOME/.gstack/chromium-profile"
for lf in SingletonLock SingletonSocket SingletonCookie; do rm -f "$PROF/$lf" 2>/dev/null || true; done
"$B" status 2>/dev/null | grep -q "Mode: headed" || "$B" connect 2>&1 | tail -3

echo "=== navigate ==="
"$B" goto "$URL" 2>&1 | tail -2
"$B" wait --load 2>&1 | tail -1

# start playback muted, then read duration ONLY once no ad is showing AND metadata is ready.
# Two traps: (a) reading right after play() returns NaN; (b) the 'ad-showing' class is set a
# few hundred ms AFTER play(), so a separate "break when no ad" loop would exit on iter 0 and
# we'd read the pre-roll AD's duration (capturing only the ad). One merged loop never accepts
# a duration while an ad is showing, and clicks the skip button when present.
DUR=$("$B" js "(async()=>{
  const v=document.querySelector('video'); if(!v) return 'DUR=0';
  v.muted=true; v.play().catch(()=>{});
  const p=document.querySelector('#movie_player');
  for(let i=0;i<60;i++){                        // ~30s: skip/await ad, THEN require real metadata
    const ad=p&&p.classList&&p.classList.contains('ad-showing');
    if(!ad && v.readyState>=1 && isFinite(v.duration) && v.duration>0) break;
    const sk=document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern'); if(sk) sk.click();
    await new Promise(r=>setTimeout(r,500));
  }
  return 'DUR='+Math.floor(v.duration||0);      // sentinel so a stray stdout line can't poison the value
})()" 2>/dev/null | grep -oE 'DUR=[0-9]+' | tail -1 | tr -dc '0-9')
[ -z "$END" ] && END="${DUR:-0}"
echo "duration=${DUR:-?} capturing ${START}..${END} step ${STEP}"
[ "${END:-0}" -le 0 ] && { echo "ERR: no <video> or unknown duration"; exit 1; }

# robust seek: pause, set time, wait 'seeked' then a presented frame, then settle
seek() {
  "$B" js "(async()=>{const v=document.querySelector('video');v.pause();await new Promise((res)=>{let s=false;const ok=()=>{if(s)return;s=true;res();};v.addEventListener('seeked',()=>{if(v.requestVideoFrameCallback){v.requestVideoFrameCallback(ok);}else{setTimeout(ok,400);}},{once:true});v.currentTime=$1;setTimeout(ok,5000);});await new Promise(r=>setTimeout(r,250));return 1})()" >/dev/null 2>&1
}

t=$START
while [ "$t" -le "$END" ]; do
  seek "$t"
  idx=$(printf "%05d" "$t")
  if "$B" screenshot "video" "$OUT/f${idx}.png" >/dev/null 2>&1 && [ -s "$OUT/f${idx}.png" ]; then
    echo "captured t=$t"
  else
    echo "WARN: screenshot failed at t=$t"
  fi
  t=$((t+STEP))
done
N=$(ls "$OUT"/*.png 2>/dev/null | wc -l | tr -d ' ')
echo "DONE: $N frames in $OUT"
[ "$N" -gt 0 ] || { echo "ERR: captured 0 frames — playback/seek/screenshot all failed"; exit 1; }
