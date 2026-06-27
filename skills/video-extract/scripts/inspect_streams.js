// inspect_streams.js — run in the video page via:  browse eval <path>
// Reports whether media is SABR-only (no GET url) so you know download is impossible.
(() => {
  let pr = null;
  try { pr = document.querySelector('#movie_player').getPlayerResponse(); } catch (e) {}
  if (!pr && window.ytInitialPlayerResponse) pr = window.ytInitialPlayerResponse;
  if (!pr || !pr.streamingData) return JSON.stringify({ error: 'no streamingData' });
  const sd = pr.streamingData;
  const fmts = [].concat(sd.adaptiveFormats || [], sd.formats || []);
  const withUrl = fmts.filter(f => f.url).length;
  const withCipher = fmts.filter(f => f.signatureCipher || f.cipher).length;
  return JSON.stringify({
    total: fmts.length,
    hasDirectUrl: withUrl,
    hasCipher: withCipher,
    sabrOnly: withUrl === 0 && withCipher === 0,
    verdict: (withUrl === 0 && withCipher === 0)
      ? 'SABR-only: no downloadable URL — use browser screenshot path'
      : 'Some formats downloadable — fast path may work',
    audioFormats: fmts.filter(f => (f.mimeType||'').startsWith('audio'))
      .map(f => ({ itag: f.itag, mime: (f.mimeType||'').split(';')[0], hasUrl: !!f.url, hasCipher: !!(f.signatureCipher||f.cipher) }))
  }, null, 1);
})()
