---
name: video-extract
description: Extract content from a YouTube or web video that won't download normally — pulls slides/keyframes (read with vision) and an optional speech transcript. Use when asked to "read / watch / summarize / transcribe a video", "what's in this video", "看视频里讲了什么", or when yt-dlp fails with HTTP 403 / SABR-only / PO-token / "Requested format is not available". Tries a fast yt-dlp path first, then falls back to driving a real headed browser (GStack browse) to play + seek + screenshot.
---

# video-extract

Turn a video URL into readable content — keyframes/slides you can SEE and (optionally) a speech transcript — even when the platform blocks normal downloads.

You (Claude) drive this skill: run the helper scripts in `scripts/`, look at what comes back, and decide the next step. The scripts do the mechanical work; you make the judgment calls (slideshow vs motion video, how finely to sample, read frames yourself vs fan out to subagents).

## Decision tree (follow in order)

1. **Probe** — `scripts/probe.sh <url> <workdir>`
   - Prints title, duration, uploader, and whether captions/subtitles exist.
   - If **captions exist** → `scripts/probe.sh` already saved them; that IS your transcript. Skip audio download.

2. **Fast path (yt-dlp)** — `scripts/fast_download.sh <url> <workdir>`
   - Escalates: plain → `--cookies-from-browser chrome --js-runtimes node` → bgutil PO-token. Downloads `audio.*` and a low-res `video.*`.
   - Exit 0 = success → go to step 4 (frames) and step 5 (transcribe). Exit 1 = blocked → step 3.

3. **Browser fallback** (when fast path fails with 403 / SABR / PO-token) — see **Browser fallback** below. This is the reliable path for modern YouTube.

4. **Frames → unique slides/scenes**
   - Build contact sheets: `scripts/contact_sheet.sh <framedir> <out.png>`. Look at them to map unique slides → timestamps (slideshow) or pick representative scenes (motion video).
   - Re-capture the unique ones at full res if needed, then **read them**. For >~6 frames, fan out with a Workflow (one subagent per frame, schema-extract title/text/chart-data); for a few, read directly.

5. **Audio → transcript**
   - If you have `audio.*`: `scripts/transcribe.sh <workdir>/audio.mp3 <workdir> <model>` (model: `small` balanced, `base` fast, `large` accurate).
   - If SABR blocked the download: options are (a) captions if any (step 1), (b) real-time capture in the browser (~video length, see Browser fallback → Audio), (c) deliver visual-only and say so plainly.

## Browser fallback (the reliable path)

Modern YouTube serves media over **SABR** (POST+protobuf, no GET URL) gated by a **PO-token bound to the video id**, so yt-dlp/curl get 403. A real browser plays fine because it mints a valid token. So: play it in a headed browser and screenshot.

1. **Capture frames** — `scripts/browse_capture.sh <url> <workdir> <start> <end> <step>`
   - Connects GStack browse (headed Chromium, anti-bot), navigates, plays muted, then seeks every `<step>` seconds from `<start>` to `<end>` and screenshots the `<video>` element to `<workdir>/frames/`.
   - First pass: coarse `step` (e.g. 50) to map the deck. Then re-capture unique slides with a small `step` window for clarity.
   - **The seek waits for `requestVideoFrameCallback`** — this kills the stale-frame race where a screenshot shows the PREVIOUS slide. Do not remove it.
2. **Enumerate completeness** — for slide decks, the PowerPoint/Keynote navigator panel and a "Slide X of N" status bar are often visible. Read them (or crop+upscale the navigator with ffmpeg) to confirm you captured every slide; presenters often linger on a few and skip others.
3. **Audio (only if user needs the spoken track and no captions exist)** — `scripts/record_audio_browser.sh <workdir> <seconds>` plays 1x and records via MediaRecorder. Costs ~video length in wall-clock. Then `scripts/transcribe.sh`.

## Gotchas (learned the hard way — see reference/gotchas.md)

- `hasUrl:false` for every format in `ytInitialPlayerResponse.streamingData` ⇒ SABR-only ⇒ no direct download. Inspect with `browse eval scripts/inspect_streams.js` (`js <expr>` is for inline code; `eval <file>` runs a script file).
- bgutil PO-token provider needs **node + the `canvas` npm package** built into its `server/` dir; even then HLS/SABR may still 403. `scripts/setup_potoken.sh` sets it up idempotently.
- Browser seek+screenshot: ALWAYS `await requestVideoFrameCallback` after `seeked`, plus a small settle, before screenshotting.
- A timestamp does NOT map to deck order — live presenters jump around. Identify slides by content, not by assumed position.
- zsh: `rm -f foo.*` errors on no-match and aborts `&&` chains — use explicit names or `2>/dev/null; true`.

## Output

Deliver: (1) a structured slide/scene-by-scene content extraction with chart data verbatim, (2) a synthesis of the argument/thesis, (3) the transcript if obtained, (4) an explicit note of anything not captured (skipped slides, audio when blocked) and how to get it.
