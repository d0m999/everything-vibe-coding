#!/usr/bin/env bash
# record_audio_browser.sh <workdir> <seconds>
# Last-resort audio capture when media is SABR-locked: play the already-open video
# 1x in GStack browse and record the tab audio via Web Audio + MediaRecorder, then
# pull the blob out as a base64 file and decode to webm. Costs ~<seconds> wall-clock.
# PRE-REQ: browse_capture.sh (or a manual goto) already loaded the video page.
set -uo pipefail
WORK="${1:?usage: record_audio_browser.sh <workdir> <seconds>}"
SECS="${2:?usage: record_audio_browser.sh <workdir> <seconds>}"
mkdir -p "$WORK"
# clear stale outputs: ffmpeg leaves a prior audio.mp3 intact when it fails on an empty webm,
# so without this a failed capture would pass the final [ -s audio.mp3 ] guard with OLD audio.
rm -f "$WORK/audio.webm" "$WORK/audio.mp3" "$WORK/audio_b64.txt" 2>/dev/null || true
# resolve gstack browse binary (repo-vendored first, then user-level) — keep in sync with browse_capture.sh
B=""
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
[ -n "$_ROOT" ] && [ -x "$_ROOT/.claude/skills/gstack/browse/dist/browse" ] && B="$_ROOT/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && [ -x "$HOME/.claude/skills/gstack/browse/dist/browse" ] && B="$HOME/.claude/skills/gstack/browse/dist/browse"
[ -x "$B" ] || { echo "ERR: gstack browse not found"; exit 1; }

echo "=== start recording + play 1x (will run ~${SECS}s) ==="
REC=$("$B" js "(async()=>{const v=document.querySelector('video');if(!v)return 'novideo';
  const ac=new (window.AudioContext||window.webkitAudioContext)();
  const src=ac.createMediaElementSource(v);const dest=ac.createMediaStreamDestination();
  src.connect(dest);src.connect(ac.destination);
  const mr=new MediaRecorder(dest.stream,{mimeType:'audio/webm'});window.__chunks=[];
  mr.ondataavailable=e=>{if(e.data.size)window.__chunks.push(e.data)};
  window.__mr=mr;mr.start();v.muted=false;v.currentTime=0;v.playbackRate=1;await v.play();
  return 'recording';})()" 2>&1 | tail -1)
echo "$REC"
[ "$REC" = novideo ] && { echo "ERR: no <video> on page — open it via browse_capture.sh (or a manual goto) first"; exit 1; }

# poll until video ends (browse keeps the page alive across calls)
i=0; lim=$(( (SECS/5) + 6 ))
while [ "$i" -lt "$lim" ]; do
  st=$("$B" js "(()=>{const v=document.querySelector('video');return (v.ended||v.currentTime>=v.duration-1)?'done':('t='+Math.floor(v.currentTime)+'/'+Math.floor(v.duration));})()" 2>/dev/null | tail -1)
  echo "$st"
  echo "$st" | grep -q done && break
  i=$((i+1))
  "$B" js "(async()=>{await new Promise(r=>setTimeout(r,5000));return 1})()" >/dev/null 2>&1
done

echo "=== stop + encode base64 (chunked) ==="
# Encode in 32KB blocks (String.fromCharCode.apply on the whole buffer overflows the
# call stack for long recordings). Stash the b64 string + its length on window.
"$B" js "(async()=>{await new Promise(res=>{window.__mr.onstop=res;window.__mr.stop();});
  const b=new Blob(window.__chunks,{type:'audio/webm'});const buf=await b.arrayBuffer();
  const u=new Uint8Array(buf);let s='';const CH=0x8000;
  for(let i=0;i<u.length;i+=CH){s+=String.fromCharCode.apply(null,u.subarray(i,i+CH));}
  window.__b64=btoa(s);window.__b64len=window.__b64.length;
  return 'bytes='+u.length+' b64len='+window.__b64.length;})()" 2>&1 | tail -1

# Pull the b64 string out in slices, not as one giant stdout line (which tail -1 could
# truncate or confuse with a status line). substr offsets are safe to split/rejoin.
B64LEN=$("$B" js "(()=>String(window.__b64len||0))()" 2>/dev/null | tail -1 | tr -dc '0-9')
echo "b64len=${B64LEN:-0}"
: > "$WORK/audio_b64.txt"
if [ "${B64LEN:-0}" -gt 0 ]; then
  CHUNK=500000; off=0
  while [ "$off" -lt "$B64LEN" ]; do
    "$B" js "(()=>window.__b64.substr($off,$CHUNK))()" 2>/dev/null | tail -1 | tr -d '\r\n' >> "$WORK/audio_b64.txt"
    off=$((off+CHUNK))
  done
fi
# Integrity: assembled file must equal the reported b64 length. A silently-dropped 500000-char
# chunk stays 4-aligned, so it would still base64-decode into corrupt audio — catch it loudly.
GOT=$(wc -c < "$WORK/audio_b64.txt" | tr -d ' ')
if [ "${B64LEN:-0}" -gt 0 ] && [ "$GOT" != "$B64LEN" ]; then
  echo "ERR: b64 assembly incomplete ($GOT/$B64LEN chars)"; exit 1
fi
# Decode via STDIN: BSD/macOS base64 rejects a positional input file (exit 64); only -i FILE or stdin work.
base64 -d < "$WORK/audio_b64.txt" > "$WORK/audio.webm" 2>/dev/null \
  || base64 -D < "$WORK/audio_b64.txt" > "$WORK/audio.webm" 2>/dev/null
command -v ffmpeg >/dev/null 2>&1 || { echo "ERR: ffmpeg not installed (needed to decode the recording)"; exit 1; }
ffmpeg -y -i "$WORK/audio.webm" -ar 16000 -ac 1 "$WORK/audio.mp3" >/dev/null 2>&1
ls -lh "$WORK/audio.webm" "$WORK/audio.mp3" 2>/dev/null
if [ -s "$WORK/audio.mp3" ]; then
  echo "DONE -> $WORK/audio.mp3 (feed to transcribe.sh)"
else
  echo "ERR: no audio captured (empty/garbled recording); $WORK/audio.mp3 missing or empty"; exit 1
fi
