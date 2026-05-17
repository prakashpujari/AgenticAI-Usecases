/**
 * Vercel Edge Function: fetch YouTube transcript.
 *
 * Edge runtime runs on Vercel's global edge network (Cloudflare-like nodes),
 * which uses different IP ranges from both Render (AWS) and Vercel Lambda.
 * YouTube does not aggressively filter edge/CDN IP ranges the same way it
 * filters known cloud-provider datacenter IPs.
 *
 * Returns 200 { transcript, method } on success.
 * Returns 502 { error, details }      if all methods fail.
 */

export const config = { runtime: 'edge' }

export default async function handler(req) {
  const url = new URL(req.url)
  const videoId = url.searchParams.get('videoId')

  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Content-Type': 'application/json',
  }

  if (req.method === 'OPTIONS')
    return new Response(null, { status: 200, headers: cors })

  if (!videoId || !/^[A-Za-z0-9_-]{11}$/.test(videoId))
    return new Response(JSON.stringify({ error: 'Invalid videoId' }), { status: 400, headers: cors })

  const errors = []

  // ── Method 1: InnerTube get_transcript (direct API call) ─────────────────
  try {
    const text = await fetchViaInnerTube(videoId)
    if (text.length > 50)
      return new Response(JSON.stringify({ transcript: text, method: 'innertube' }), { headers: cors })
    errors.push('innertube: too short')
  } catch (e) {
    errors.push(`innertube: ${e.message}`)
  }

  // ── Method 2: watch-page scrape + session-cookie caption download ─────────
  try {
    const text = await fetchViaWatchPage(videoId)
    if (text.length > 50)
      return new Response(JSON.stringify({ transcript: text, method: 'watchpage' }), { headers: cors })
    errors.push('watchpage: too short')
  } catch (e) {
    errors.push(`watchpage: ${e.message}`)
  }

  // ── Method 3: old timedtext endpoint ──────────────────────────────────────
  try {
    const text = await fetchViaTimedtext(videoId)
    if (text.length > 50)
      return new Response(JSON.stringify({ transcript: text, method: 'timedtext' }), { headers: cors })
    errors.push('timedtext: too short')
  } catch (e) {
    errors.push(`timedtext: ${e.message}`)
  }

  return new Response(
    JSON.stringify({ error: 'youtube_proxy_failed', details: errors }),
    { status: 502, headers: cors }
  )
}

// ── Helpers (Edge-compatible: only fetch(), no Node.js APIs) ──────────────

const BROWSER_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

const BROWSER_HEADERS = {
  'User-Agent': BROWSER_UA,
  'Accept-Language': 'en-US,en;q=0.9',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Sec-Fetch-Mode': 'navigate',
  'Sec-Fetch-Site': 'none',
}

// Base64-encode a string (Edge-safe, no Buffer)
function b64(str) {
  return btoa(String.fromCharCode(...new TextEncoder().encode(str)))
}

async function fetchViaInnerTube(videoId) {
  const body = JSON.stringify({
    context: {
      client: {
        clientName: 'WEB',
        clientVersion: '2.20240101.00.00',
        hl: 'en', gl: 'US',
        userAgent: BROWSER_UA,
      },
    },
    videoId,
    params: b64(`\n\x0b${videoId}`),
  })

  const resp = await fetch(
    'https://www.youtube.com/youtubei/v1/get_transcript?prettyPrint=false',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': BROWSER_UA,
        'X-YouTube-Client-Name': '1',
        'X-YouTube-Client-Version': '2.20240101.00.00',
        'Origin': 'https://www.youtube.com',
        'Referer': `https://www.youtube.com/watch?v=${videoId}`,
      },
      body,
    }
  )

  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const data = await resp.json()

  // Parse transcript segments from the response
  const segments =
    data?.actions?.[0]?.updateEngagementPanelAction?.content
      ?.transcriptRenderer?.content?.transcriptSearchPanelRenderer
      ?.body?.transcriptSegmentListRenderer?.initialSegments || []

  const texts = segments
    .map(s => s?.transcriptSegmentRenderer?.snippet?.runs
      ?.map(r => r.text).join('') || '')
    .filter(Boolean)

  if (!texts.length) throw new Error('No segments in InnerTube response')
  return texts.join(' ')
}

async function fetchViaWatchPage(videoId) {
  const watchUrl = `https://www.youtube.com/watch?v=${videoId}&hl=en&gl=US`
  const watchResp = await fetch(watchUrl, { headers: BROWSER_HEADERS })
  const html = await watchResp.text()

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

  const track =
    tracks.find(t => t.languageCode?.startsWith('en') && t.kind === 'asr') ||
    tracks.find(t => t.languageCode?.startsWith('en')) ||
    tracks[0]

  const setCookie = watchResp.headers.get('set-cookie') || ''
  const cookieStr = setCookie
    .split(/,(?=[^;]+=[^;]+;)/)
    .map(c => c.split(';')[0].trim())
    .join('; ')

  const capResp = await fetch(track.baseUrl + '&fmt=json3', {
    headers: {
      'User-Agent': BROWSER_UA,
      'Referer': watchUrl,
      ...(cookieStr ? { Cookie: cookieStr } : {}),
    },
  })

  const body = await capResp.text()
  if (!body || body.length < 10) throw new Error('Caption response empty')

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
  const resp = await fetch(url, { headers: { 'User-Agent': BROWSER_UA } })
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
