# video-extract — gotchas & rationale

Hard-won notes from building this pipeline against modern YouTube (2026).

## Why yt-dlp fails on modern YouTube
- **SABR streaming**: the WEB client fetches media via POST requests with a protobuf
  body (Server ABR). In `ytInitialPlayerResponse.streamingData`, every format has
  `url:false` and `signatureCipher:false` — there is no GET URL to download. ffmpeg/curl
  can't reconstruct the SABR protocol practically. Detect with `inspect_streams.js`.
- **PO-Token bound to video id**: yt-dlp logs `Detected experiment to bind GVS PO Token
  to video id`. Without a valid Proof-of-Origin token the CDN (`*.googlevideo.com`)
  returns **HTTP 403** on every segment — even though the youtube.com API calls succeed.
  Symptom: metadata works, media 403s.
- `--force-ipv4` / retries don't help; it's token/protocol, not network.

## PO-token provider (bgutil) — when it helps and when it doesn't
- Plugin: `pip install bgutil-ytdlp-pot-provider`. It needs a generator: either an HTTP
  server (`:4416`) or the **script mode** at `~/bgutil-ytdlp-pot-provider/server/build/generate_once.js`.
- Build the generator: clone the repo at the matching version tag, `cd server && npm install && npx tsc`.
- **canvas**: the botguard challenge runs in jsdom and needs the `canvas` npm package in
  `server/node_modules`, else you get `HTMLCanvasElement getContext not implemented` and a
  possibly-invalid token. Install it inside `server/`.
- Also pass `--js-runtimes node` so yt-dlp can solve the n-sig JS challenge.
- Reality: even with a generated token, HLS/SABR for token-bound videos may STILL 403,
  because jsdom botguard can be detected as non-browser. That's why the browser path exists.

## The browser is the reliable path
A real headed browser (GStack browse, or Playwright with a stealth/extension bridge)
mints a valid PO-token and plays the media. You can't easily pull the SABR stream out,
but you can **seek + screenshot the `<video>` element** to get every frame you need.

### Stale-frame race (critical)
After `video.currentTime = t`, the displayed frame lags. If you screenshot immediately
you capture the PREVIOUS position — symptom: the same timestamp yields different slides
on different runs. Fix: wait for `seeked` THEN `requestVideoFrameCallback` (the next
actually-presented frame), then a small settle (~250ms), THEN screenshot. Baked into
`browse_capture.sh`.

### Mapping coverage
- Timestamp ≠ deck order. Live presenters jump around and linger on a few slides; some
  slides never hit the main pane. Identify slides by CONTENT, not assumed position.
- For PowerPoint/Keynote recordings, the navigator panel + "Slide X of N" status bar tell
  you the true slide count and titles. Crop+upscale the navigator with ffmpeg to enumerate.
- Use contact sheets (ffmpeg `tile`) to map many frames at once, then re-capture uniques
  full-res for accurate chart-number reading.

## Reading frames at scale
For more than a handful of frames, fan out with a Workflow: one subagent per frame with a
StructuredOutput schema (title, subtitle, body_text verbatim, charts with every numeric
value, key_figures, source, navigator_titles). Then synthesize. Subagents can Read image
files by absolute path.

## Audio when SABR-blocked
1. Captions/auto-captions if any (fastest) — `probe.sh` fetches them.
2. Real-time MediaRecorder capture in the browser — `record_audio_browser.sh`. Plays 1x,
   records tab audio via Web Audio, exports the blob as base64, decodes to mp3. Costs
   ~video length in wall-clock; pitch/speed must stay 1x for whisper.
3. Otherwise: deliver visual-only and say so plainly.

## Shell footguns
- zsh: `rm -f foo.*` ERRORS on no-match and aborts the `&&` chain. Use explicit filenames
  or `rm -f a b c 2>/dev/null; true`.
- Don't pipe long-running yt-dlp/ffmpeg through `tail` when you want to watch progress in a
  backgrounded task — `tail` buffers until EOF. Read the raw output file instead.
- Foreground `sleep` may be blocked by the harness; do waits browser-side (setTimeout in
  `js`) or poll inside a script loop.
