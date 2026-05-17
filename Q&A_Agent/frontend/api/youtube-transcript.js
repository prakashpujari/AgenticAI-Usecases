/**
 * Vercel serverless function: fetch YouTube transcript.
 *
 * Called by the frontend when a YouTube URL is submitted. Runs on Vercel's
 * infrastructure (different IP range from Render), which is not in YouTube's
 * datacenter-IP block list. If successful the frontend sends the transcript
 * text as a .txt file to the Render backend, bypassing Render's YouTube path.
 *
 * Three methods tried in order:
 *   1. youtube-transcript npm package  (InnerTube API)
 *   2. Watch-page scrape + caption URL (session-aware)
 *   3. Old timedtext endpoint          (legacy, sometimes works)
 */

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS')

  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'GET')
    return res.status(405).json({ error: 'Method not allowed' })

  const { videoId } = req.query
  if (!videoId || !/^[A-Za-z0-9_-]{11}$/.test(videoId))
    return res.status(400).json({ error: 'Invalid videoId' })

  const errors = []

  // ── Method 1: youtube-transcript package ─────────────────────────────────
  try {
    const { YoutubeTranscript } = await import('youtube-transcript')
    const items = await YoutubeTranscript.fetchTranscript(videoId, { lang: 'en' })
    const text = items
      .map(i => (i.text || '').replace(/\n/g, ' ').trim())
      .filter(Boolean)
      .join(' ')
    if (text.length > 50) {
      return res.json({ transcript: text, method: 'youtube-transcript' })
    }
    errors.push('youtube-transcript: empty result')
  } catch (e) {
    errors.push(`youtube-transcript: ${e.message}`)
  }

  // ── Method 2: watch-page scrape + caption URL ─────────────────────────────
  try {
    const text = await fetchViaWatchPage(videoId)
    if (text.length > 50) {
      return res.json({ transcript: text, method: 'watchpage' })
    }
    errors.push('watchpage: empty caption')
  } catch (e) {
    errors.push(`watchpage: ${e.message}`)
  }

  // ── Method 3: old timedtext endpoint ──────────────────────────────────────
  try {
    const text = await fetchViaTimedtext(videoId)
    if (text.length > 50) {
      return res.json({ transcript: text, method: 'timedtext' })
    }
    errors.push('timedtext: empty result')
  } catch (e) {
    errors.push(`timedtext: ${e.message}`)
  }

  return res.status(502).json({
    error: 'All transcript methods failed from Vercel proxy',
    details: errors,
  })
}

// ── Helpers ────────────────────────────────────────────────────────────────

const BROWSER_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

async function fetchViaWatchPage(videoId) {
  const watchUrl = `https://www.youtube.com/watch?v=${videoId}&hl=en&gl=US`
  const watchResp = await fetch(watchUrl, {
    headers: {
      'User-Agent': BROWSER_UA,
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept': 'text/html,application/xhtml+xml',
    },
  })
  const html = await watchResp.text()

  // Extract ytInitialPlayerResponse JSON
  const marker = 'var ytInitialPlayerResponse = '
  const idx = html.indexOf(marker)
  if (idx === -1) throw new Error('ytInitialPlayerResponse not found')

  let depth = 0, start = idx + marker.length, end = start
  for (let i = start; i < html.length; i++) {
    if (html[i] === '{') depth++
    else if (html[i] === '}') { depth--; if (depth === 0) { end = i + 1; break } }
  }
  const player = JSON.parse(html.slice(start, end))

  const tracks =
    player?.captions?.playerCaptionsTracklistRenderer?.captionTracks || []
  if (!tracks.length) throw new Error('No caption tracks in player response')

  // Prefer English auto-generated or manual
  const track =
    tracks.find(t => t.languageCode?.startsWith('en') && t.kind === 'asr') ||
    tracks.find(t => t.languageCode?.startsWith('en')) ||
    tracks[0]

  // Collect cookies from watch page
  const setCookie = watchResp.headers.get('set-cookie') || ''
  const cookieStr = setCookie
    .split(/,(?=[^;]+=[^;]+;)/)
    .map(c => c.split(';')[0].trim())
    .join('; ')

  // Download captions with session cookies
  const capUrl = track.baseUrl + '&fmt=json3'
  const capResp = await fetch(capUrl, {
    headers: {
      'User-Agent': BROWSER_UA,
      'Referer': watchUrl,
      ...(cookieStr ? { Cookie: cookieStr } : {}),
    },
  })

  const body = await capResp.text()
  if (!body || body.length < 10) throw new Error('Caption response was empty')

  const capData = JSON.parse(body)
  const seen = new Set()
  const texts = []
  for (const event of capData.events || []) {
    for (const seg of event.segs || []) {
      const t = (seg.utf8 || '').replace(/\n/g, ' ').trim()
      if (t && !seen.has(t)) { seen.add(t); texts.push(t) }
    }
  }
  if (!texts.length) throw new Error('Caption file contained no text')
  return texts.join(' ')
}

async function fetchViaTimedtext(videoId) {
  const url =
    `https://www.youtube.com/api/timedtext` +
    `?v=${videoId}&lang=en&fmt=json3&caps=asr&xoaf=5`
  const resp = await fetch(url, {
    headers: { 'User-Agent': BROWSER_UA, 'Accept-Language': 'en-US,en;q=0.9' },
  })
  const body = await resp.text()
  if (!body || body.length < 10) throw new Error('Empty timedtext response')
  const data = JSON.parse(body)
  const texts = []
  for (const event of data.events || []) {
    for (const seg of event.segs || []) {
      const t = (seg.utf8 || '').replace(/\n/g, ' ').trim()
      if (t) texts.push(t)
    }
  }
  if (!texts.length) throw new Error('No text in timedtext response')
  return texts.join(' ')
}
