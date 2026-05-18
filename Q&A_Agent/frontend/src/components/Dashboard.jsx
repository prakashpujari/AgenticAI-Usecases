import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import {
  ComposableMap, Geographies, Geography
} from 'react-simple-maps'

const REFRESH_MS = 30_000
const GEO_URL    = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'

// ISO alpha-2 → ISO numeric (world-atlas uses geo.id = numeric string)
const A2_TO_NUM = {
  AF:'004',AL:'008',DZ:'012',AD:'020',AO:'024',AG:'028',AR:'032',AM:'051',
  AU:'036',AT:'040',AZ:'031',BS:'044',BH:'048',BD:'050',BB:'052',BY:'112',
  BE:'056',BZ:'084',BJ:'204',BT:'064',BO:'068',BA:'070',BW:'072',BR:'076',
  BN:'096',BG:'100',BF:'854',BI:'108',CV:'132',KH:'116',CM:'120',CA:'124',
  CF:'140',TD:'148',CL:'152',CN:'156',CO:'170',KM:'174',CD:'180',CG:'178',
  CR:'188',HR:'191',CU:'192',CY:'196',CZ:'203',DK:'208',DJ:'262',DM:'212',
  DO:'214',EC:'218',EG:'818',SV:'222',GQ:'226',ER:'232',EE:'233',SZ:'748',
  ET:'231',FJ:'242',FI:'246',FR:'250',GA:'266',GM:'270',GE:'268',DE:'276',
  GH:'288',GR:'300',GD:'308',GT:'320',GN:'324',GW:'624',GY:'328',HT:'332',
  HN:'340',HU:'348',IS:'352',IN:'356',ID:'360',IR:'364',IQ:'368',IE:'372',
  IL:'376',IT:'380',JM:'388',JP:'392',JO:'400',KZ:'398',KE:'404',KI:'296',
  KP:'408',KR:'410',KW:'414',KG:'417',LA:'418',LV:'428',LB:'422',LS:'426',
  LR:'430',LY:'434',LI:'438',LT:'440',LU:'442',MG:'450',MW:'454',MY:'458',
  MV:'462',ML:'466',MT:'470',MH:'584',MR:'478',MU:'480',MX:'484',FM:'583',
  MD:'498',MC:'492',MN:'496',ME:'499',MA:'504',MZ:'508',MM:'104',NA:'516',
  NR:'520',NP:'524',NL:'528',NZ:'554',NI:'558',NE:'562',NG:'566',NO:'578',
  OM:'512',PK:'586',PW:'585',PA:'591',PG:'598',PY:'600',PE:'604',PH:'608',
  PL:'616',PT:'620',QA:'634',RO:'642',RU:'643',RW:'646',KN:'659',LC:'662',
  VC:'670',WS:'882',SM:'674',ST:'678',SA:'682',SN:'686',RS:'688',SC:'690',
  SL:'694',SG:'702',SK:'703',SI:'705',SB:'090',SO:'706',ZA:'710',SS:'728',
  ES:'724',LK:'144',SD:'729',SR:'740',SE:'752',CH:'756',SY:'760',TW:'158',
  TJ:'762',TZ:'834',TH:'764',TL:'626',TG:'768',TO:'776',TT:'780',TN:'788',
  TR:'792',TM:'795',TV:'798',UG:'800',UA:'804',AE:'784',GB:'826',US:'840',
  UY:'858',UZ:'860',VU:'548',VE:'862',VN:'704',YE:'887',ZM:'894',ZW:'716',
}

// ── Small reusable primitives ──────────────────────────────────────────────────

function StatCard({ label, value, sub, color = 'indigo' }) {
  const colors = {
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-700',
    green:  'bg-green-50  border-green-200  text-green-700',
    red:    'bg-red-50    border-red-200    text-red-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    gray:   'bg-gray-50   border-gray-200   text-gray-700',
  }
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <p className="text-sm font-medium opacity-75">{label}</p>
      <p className="text-3xl font-bold mt-1">{value ?? '—'}</p>
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </div>
  )
}

function StatusBadge({ status }) {
  const map = {
    completed:  'bg-green-100  text-green-800',
    failed:     'bg-red-100    text-red-800',
    processing: 'bg-blue-100   text-blue-800',
    queued:     'bg-yellow-100 text-yellow-800',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-700'}`}>
      {status}
    </span>
  )
}

function CacheBadge({ cached }) {
  return cached
    ? <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">cached</span>
    : <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">fresh</span>
}

// ── Star Rating ────────────────────────────────────────────────────────────────

function StarRating({ value, onChange, readonly = false }) {
  const [hover, setHover] = useState(0)
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map(star => (
        <button key={star} type="button" disabled={readonly}
          onClick={() => !readonly && onChange?.(star)}
          onMouseEnter={() => !readonly && setHover(star)}
          onMouseLeave={() => !readonly && setHover(0)}
          className={`text-2xl transition-transform ${readonly ? 'cursor-default' : 'cursor-pointer hover:scale-110'}`}
        >
          <span className={(hover || value) >= star ? 'text-yellow-400' : 'text-gray-300'}>★</span>
        </button>
      ))}
    </div>
  )
}

function RatingBar({ star, count, total }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-4 text-right text-gray-600 font-medium">{star}</span>
      <span className="text-yellow-400 text-sm">★</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className="h-2 rounded-full bg-yellow-400 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-gray-500">{count}</span>
    </div>
  )
}

// ── Confirm Modal ──────────────────────────────────────────────────────────────

function ConfirmModal({ message, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
        <p className="text-gray-800 font-medium mb-5">{message}</p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel}
            className="px-4 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
          <button onClick={onConfirm}
            className="px-4 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700">
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Review Form ────────────────────────────────────────────────────────────────

const USE_CASES = ['', 'Education / Study', 'Interview Prep', 'Quiz Creation', 'Research', 'Corporate Training', 'Content Creation', 'Other']

function ReviewForm({ onSubmitted }) {
  const [rating, setRating]             = useState(0)
  const [text, setText]                 = useState('')
  const [useCase, setUseCase]           = useState('')
  const [reviewerName, setReviewerName] = useState('')
  const [submitting, setSubmitting]     = useState(false)
  const [done, setDone]                 = useState(false)
  const [err, setErr]                   = useState('')

  const handleSubmit = async e => {
    e.preventDefault()
    if (!rating) { setErr('Please select a star rating.'); return }
    setSubmitting(true); setErr('')
    try {
      await axios.post('/api/reviews', { rating, review_text: text, use_case: useCase, reviewer_name: reviewerName.trim() })
      setDone(true); onSubmitted?.()
    } catch { setErr('Failed to submit — please try again.') }
    finally { setSubmitting(false) }
  }

  if (done) return (
    <div className="text-center py-6">
      <div className="text-4xl mb-2">🎉</div>
      <p className="font-semibold text-green-700">Thank you for your feedback!</p>
    </div>
  )

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Your Name <span className="text-gray-400 font-normal">(optional)</span>
        </label>
        <input type="text" value={reviewerName} onChange={e => setReviewerName(e.target.value)}
          maxLength={80} placeholder="e.g. Alice"
          className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Your Rating</label>
        <StarRating value={rating} onChange={setRating} />
        {rating > 0 && <p className="text-xs text-gray-500 mt-1">{['','Poor','Fair','Good','Very Good','Excellent'][rating]}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Use Case (optional)</label>
        <select value={useCase} onChange={e => setUseCase(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400">
          {USE_CASES.map(u => <option key={u} value={u}>{u || '— Select —'}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Review (optional)</label>
        <textarea value={text} onChange={e => setText(e.target.value)} maxLength={2000} rows={3}
          placeholder="What worked well? What could be better?"
          className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        <p className="text-xs text-gray-400 text-right">{text.length}/2000</p>
      </div>
      {err && <p className="text-sm text-red-600">{err}</p>}
      <button type="submit" disabled={submitting}
        className="w-full py-2 px-4 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 transition">
        {submitting ? 'Submitting…' : 'Submit Review'}
      </button>
    </form>
  )
}

// ── Review Card with Replies ───────────────────────────────────────────────────

function ReplyBox({ reviewId, onReplied }) {
  const [text, setText]       = useState('')
  const [name, setName]       = useState('')
  const [posting, setPosting] = useState(false)
  const [err, setErr]         = useState('')

  const submit = async () => {
    if (!text.trim()) return
    setPosting(true); setErr('')
    try {
      await axios.post(`/api/reviews/${reviewId}/reply`, { text: text.trim(), reviewer_name: name.trim() })
      setText(''); setName(''); onReplied?.()
    } catch { setErr('Failed to post reply.') }
    finally { setPosting(false) }
  }

  return (
    <div className="mt-2 space-y-2 border-t border-gray-100 pt-2">
      <input type="text" value={name} onChange={e => setName(e.target.value)}
        placeholder="Your name (optional)" maxLength={80}
        className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-300" />
      <textarea value={text} onChange={e => setText(e.target.value)} rows={2}
        placeholder="Write a reply…"
        className="w-full text-xs border border-gray-200 rounded px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-300" />
      {err && <p className="text-xs text-red-500">{err}</p>}
      <div className="flex gap-2">
        <button onClick={submit} disabled={posting || !text.trim()}
          className="px-3 py-1 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-700 disabled:opacity-50">
          {posting ? 'Posting…' : 'Post Reply'}
        </button>
      </div>
    </div>
  )
}

function ReviewCard({ review, onReplyPosted }) {
  const [showReply, setShowReply] = useState(false)
  const date = review.created_at ? new Date(review.created_at).toLocaleDateString() : '—'
  const sentimentColor = { positive: 'text-green-600', neutral: 'text-gray-500', negative: 'text-red-500' }[review.sentiment] ?? 'text-gray-400'
  const initials = review.reviewer_name
    ? review.reviewer_name.trim().split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : '?'

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center flex-shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 truncate">
            {review.reviewer_name || <span className="text-gray-400 font-normal italic">Anonymous</span>}
          </p>
          <p className="text-xs text-gray-400">{date}</p>
        </div>
        {review.rating > 0 && <StarRating value={review.rating} readonly />}
      </div>

      {review.use_case && (
        <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium">
          {review.use_case}
        </span>
      )}
      {review.review_text && <p className="text-sm text-gray-700 leading-relaxed">{review.review_text}</p>}
      {review.sentiment && (
        <p className={`text-xs font-medium ${sentimentColor}`}>
          Sentiment: {review.sentiment}{review.sentiment_score != null && ` (${review.sentiment_score.toFixed(2)})`}
        </p>
      )}

      {/* Nested replies */}
      {review.replies?.length > 0 && (
        <div className="ml-4 border-l-2 border-indigo-100 pl-3 space-y-2">
          {review.replies.map(reply => (
            <div key={reply.review_id} className="text-sm space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-gray-700 text-xs">
                  {reply.reviewer_name || 'Anonymous'}
                </span>
                <span className="text-xs text-gray-400">{reply.created_at ? new Date(reply.created_at).toLocaleDateString() : ''}</span>
              </div>
              <p className="text-gray-600 text-xs">{reply.review_text}</p>
            </div>
          ))}
        </div>
      )}

      {/* Reply toggle */}
      <button onClick={() => setShowReply(s => !s)}
        className="text-xs text-indigo-600 hover:underline mt-1">
        {showReply ? 'Cancel' : '↩ Reply'}
      </button>
      {showReply && (
        <ReplyBox reviewId={review.review_id} onReplied={() => { setShowReply(false); onReplyPosted?.() }} />
      )}
    </div>
  )
}

// ── World Map ─────────────────────────────────────────────────────────────────

function WorldMap({ byCountry, total }) {
  const [tooltip, setTooltip] = useState(null)   // { name, count, pct, avg_ms, x, y }

  // Build numeric-id → row map  (world-atlas geo.id is the 3-digit ISO numeric)
  const dataByNum = {}
  ;(byCountry || []).forEach(c => {
    const num = A2_TO_NUM[c.country_code]
    if (num) dataByNum[num] = c
  })
  const maxCount = Math.max(1, ...Object.values(dataByNum).map(c => c.count))

  if (!byCountry || byCountry.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Access by Location</h3>
        <div className="text-center text-gray-400 text-sm py-12">
          No geographic data yet — submit a job from the app to populate this map.
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 relative">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">Access by Location</h3>
      <p className="text-xs text-gray-400 mb-3">Hover a country for details</p>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-20 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 pointer-events-none shadow-lg"
          style={{ left: tooltip.x + 12, top: tooltip.y - 40 }}
        >
          <p className="font-semibold">{tooltip.name}</p>
          <p>{tooltip.count} request{tooltip.count !== 1 ? 's' : ''} · {tooltip.pct}%</p>
          {tooltip.avg_ms > 0 && <p>Avg latency: {tooltip.avg_ms.toFixed(0)} ms</p>}
        </div>
      )}

      {/* Map — no ZoomableGroup (removed in react-simple-maps v3) */}
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ scale: 130, center: [10, 20] }}
        width={780}
        height={380}
        style={{ width: '100%', height: 'auto' }}
      >
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map(geo => {
              const geoId = geo.id != null
                ? String(parseInt(String(geo.id), 10)).padStart(3, '0')
                : ''
              const row   = dataByNum[geoId]
              const count = row?.count || 0
              const intensity = count > 0 ? 0.25 + 0.75 * (count / maxCount) : 0
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={count > 0 ? `rgba(79,70,229,${intensity.toFixed(2)})` : '#E5E7EB'}
                  stroke="#fff"
                  strokeWidth={0.4}
                  style={{
                    default: { outline: 'none' },
                    hover:   { fill: count > 0 ? '#312e81' : '#D1D5DB', outline: 'none', cursor: count > 0 ? 'pointer' : 'default' },
                    pressed: { outline: 'none' },
                  }}
                  onMouseEnter={e => {
                    if (!count) return
                    const pct = total > 0 ? ((count / total) * 100).toFixed(1) : 0
                    setTooltip({
                      name:   geo.properties.name || geoId,
                      count,
                      pct,
                      avg_ms: row?.avg_ms || 0,
                      x: e.clientX - e.currentTarget.closest('.relative').getBoundingClientRect().left,
                      y: e.clientY - e.currentTarget.closest('.relative').getBoundingClientRect().top,
                    })
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              )
            })
          }
        </Geographies>
      </ComposableMap>

      {/* Colour legend */}
      <div className="flex items-center gap-2 mt-2">
        <span className="text-xs text-gray-400">Less</span>
        <div className="flex gap-0.5">
          {[0.25, 0.4, 0.55, 0.7, 0.85, 1.0].map(a => (
            <div key={a} className="w-5 h-3 rounded-sm" style={{ background: `rgba(79,70,229,${a})` }} />
          ))}
        </div>
        <span className="text-xs text-gray-400">More</span>
      </div>

      {/* Country stats table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-100">
              <th className="text-left py-1 pr-3">Country</th>
              <th className="text-right py-1 pr-3">Requests</th>
              <th className="text-right py-1 pr-3">Share</th>
              <th className="text-right py-1">Avg Latency</th>
            </tr>
          </thead>
          <tbody>
            {byCountry.slice(0, 10).map(c => {
              const pct = total > 0 ? ((c.count / total) * 100).toFixed(1) : 0
              return (
                <tr key={c.country_code} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-1.5 pr-3 font-medium text-gray-700">
                    <span className="mr-1 text-gray-400 font-mono">{c.country_code}</span>
                    {c.country || c.country_code}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-600">{c.count}</td>
                  <td className="py-1.5 pr-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <div className="w-12 bg-gray-100 rounded-full h-1.5">
                        <div className="h-1.5 rounded-full bg-indigo-500"
                          style={{ width: `${Math.min(100, pct * 2)}%` }} />
                      </div>
                      <span className="text-gray-500 w-8 text-right">{pct}%</span>
                    </div>
                  </td>
                  <td className="py-1.5 text-right font-mono text-gray-500">
                    {c.avg_ms > 0 ? `${c.avg_ms.toFixed(0)} ms` : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Analytics Section ─────────────────────────────────────────────────────────

function AnalyticsSection() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const res = await axios.get('/api/analytics')
      setData(res.data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id) }, [load])

  if (loading) return <div className="text-center text-gray-400 py-8">Loading analytics…</div>
  if (!data)   return <div className="text-center text-gray-400 py-8">No analytics data yet</div>

  const total       = data.total_requests ?? 0
  const typeData    = (data.by_type || []).map(t => ({
    name:     t.type || 'unknown',
    requests: t.count,
    avg_ms:   Math.round(t.avg_ms || 0),
  }))
  const latencyData = (data.latency_trend || [])
    .filter(t => t.avg_ms > 0)
    .map(t => ({ time: (t.hour || '').slice(11, 16) || t.hour, ms: Math.round(t.avg_ms || 0) }))

  const overallAvgMs = typeData.length
    ? Math.round(typeData.reduce((s, t) => s + t.avg_ms * t.requests, 0) /
        Math.max(1, typeData.reduce((s, t) => s + t.requests, 0)))
    : 0

  return (
    <div className="space-y-6">
      {/* KPI counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Requests" value={total} color="indigo" />
        <StatCard label="Countries"      value={(data.by_country || []).length} color="green" />
        <StatCard label="Avg Latency"    value={overallAvgMs > 0 ? `${overallAvgMs} ms` : '—'} color="gray" />
        <StatCard label="Request Types"  value={(data.by_type || []).length} color="purple" />
      </div>

      {/* World map + country table */}
      <WorldMap byCountry={data.by_country} total={total} />

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Request type — count + latency combined */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-1">Requests by Type</h3>
          <p className="text-xs text-gray-400 mb-4">Bars = request count · line = avg latency (ms)</p>
          {typeData.length === 0
            ? <p className="text-sm text-gray-400">No data yet</p>
            : (
              <>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={typeData} margin={{ top: 0, right: 30, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="ms" />
                    <Tooltip
                      formatter={(val, name) =>
                        name === 'avg_ms' ? [`${val} ms`, 'Avg Latency'] : [val, 'Requests']
                      }
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar yAxisId="left" dataKey="requests" fill="#6366f1" radius={[4,4,0,0]} name="Requests" />
                    <Line yAxisId="right" type="monotone" dataKey="avg_ms" stroke="#f59e0b"
                      strokeWidth={2} dot={{ r: 4, fill: '#f59e0b' }} name="Avg Latency (ms)" />
                  </BarChart>
                </ResponsiveContainer>
                {/* Per-type detail table */}
                <table className="w-full text-xs mt-3">
                  <thead>
                    <tr className="text-gray-500 border-b border-gray-100">
                      <th className="text-left py-1">Type</th>
                      <th className="text-right py-1">Count</th>
                      <th className="text-right py-1">Share</th>
                      <th className="text-right py-1">Avg Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {typeData.map(t => {
                      const pct = total > 0 ? ((t.requests / total) * 100).toFixed(1) : 0
                      return (
                        <tr key={t.name} className="border-b border-gray-50">
                          <td className="py-1 pr-2">
                            <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded">{t.name}</span>
                          </td>
                          <td className="py-1 text-right text-gray-700 font-medium">{t.requests}</td>
                          <td className="py-1 text-right text-gray-500">{pct}%</td>
                          <td className="py-1 text-right font-mono text-gray-500">
                            {t.avg_ms > 0 ? `${t.avg_ms} ms` : '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </>
            )
          }
        </div>

        {/* Latency trend over time */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-1">Latency Trend (last 24 h)</h3>
          <p className="text-xs text-gray-400 mb-4">Average response time per hour</p>
          {latencyData.length === 0
            ? <p className="text-sm text-gray-400">No latency data yet — submit a job first</p>
            : (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={latencyData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="ms" />
                  <Tooltip formatter={v => [`${v} ms`, 'Avg Latency']} />
                  <Line type="monotone" dataKey="ms" stroke="#6366f1" strokeWidth={2}
                    dot={{ r: 3, fill: '#6366f1' }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            )
          }
        </div>
      </div>

      {/* Recent access table */}
      {data.recent?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700">Recent Accesses</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-500 text-left uppercase tracking-wider">
                  <th className="px-4 py-2">Country</th>
                  <th className="px-4 py-2">City</th>
                  <th className="px-4 py-2">Request Type</th>
                  <th className="px-4 py-2 text-right">Latency</th>
                  <th className="px-4 py-2 text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.recent.map((r, i) => {
                  const lat = r.latency_ms
                  const latStr = lat != null && lat > 0 ? `${Math.round(lat)} ms` : lat === 0 ? '< 1 ms' : '—'
                  const latColor = lat > 1000 ? 'text-red-600' : lat > 500 ? 'text-yellow-600' : 'text-green-600'
                  return (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium">
                        <span className="text-gray-400 font-mono mr-1">{r.country_code || ''}</span>
                        {r.country || '—'}
                      </td>
                      <td className="px-4 py-2 text-gray-500">{r.city || '—'}</td>
                      <td className="px-4 py-2">
                        <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded">
                          {r.request_type || 'unknown'}
                        </span>
                      </td>
                      <td className={`px-4 py-2 text-right font-mono font-semibold ${latColor}`}>{latStr}</td>
                      <td className="px-4 py-2 text-right text-gray-400">
                        {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Files Section ─────────────────────────────────────────────────────────────

function FilesSection({ onDeleted }) {
  const [files, setFiles]         = useState([])
  const [confirm, setConfirm]     = useState(null)  // file to confirm-delete
  const [deleting, setDeleting]   = useState(null)

  const load = useCallback(async () => {
    try { const r = await axios.get('/api/files?limit=20'); setFiles(r.data.files || []) } catch {}
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (fileId) => {
    setDeleting(fileId); setConfirm(null)
    try {
      await axios.delete(`/api/files/${fileId}`)
      setFiles(f => f.filter(x => x.file_id !== fileId))
      onDeleted?.()
    } catch { alert('Failed to delete file.') }
    finally { setDeleting(null) }
  }

  if (files.length === 0) return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-400 text-sm">
      No uploaded files yet
    </div>
  )

  return (
    <>
      {confirm && (
        <ConfirmModal
          message={`Delete "${confirm.filename}"? This will also remove the generated output.`}
          onConfirm={() => handleDelete(confirm.file_id)}
          onCancel={() => setConfirm(null)}
        />
      )}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Uploaded Files</h3>
          <span className="text-xs text-gray-400">{files.length} file{files.length !== 1 ? 's' : ''}</span>
        </div>
        <div className="divide-y divide-gray-50">
          {files.map(f => (
            <div key={f.file_id} className="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
              <span className="text-xl">📄</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{f.filename}</p>
                <p className="text-xs text-gray-400">
                  {f.size_bytes ? `${(f.size_bytes / 1024).toFixed(0)} KB` : '—'}
                  {f.output_mode && ` · ${f.output_mode}`}
                  {f.job_status && (
                    <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${f.job_status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {f.job_status}
                    </span>
                  )}
                </p>
              </div>
              <span className="text-xs text-gray-400 hidden sm:block">
                {f.created_at ? new Date(f.created_at).toLocaleDateString() : '—'}
              </span>
              <button
                onClick={() => setConfirm(f)}
                disabled={deleting === f.file_id}
                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition"
                title="Delete file"
              >
                {deleting === f.file_id ? '…' : '🗑'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [stats,       setStats]       = useState(null)
  const [jobs,        setJobs]        = useState([])
  const [cache,       setCache]       = useState(null)
  const [reviews,     setReviews]     = useState([])
  const [revStats,    setRevStats]    = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [lastSync,    setLastSync]    = useState(null)
  const [showAllJobs, setShowAllJobs] = useState(false)
  const [activeTab,   setActiveTab]   = useState('overview')  // overview | analytics | files

  const fetchAll = useCallback(async () => {
    try {
      const limit = showAllJobs ? 0 : 3   // 0 = all jobs
      const [sRes, jRes, cRes, rRes] = await Promise.all([
        axios.get('/api/dashboard/stats'),
        axios.get(`/api/dashboard/jobs?limit=${limit}`),
        axios.get('/api/dashboard/cache-status'),
        axios.get('/api/dashboard/reviews?limit=10'),
      ])
      setStats(sRes.data)
      setJobs(jRes.data.jobs ?? [])
      setCache(cRes.data)
      setReviews(rRes.data.reviews ?? [])
      setRevStats(rRes.data.stats ?? null)
      setError(null)
      setLastSync(new Date().toLocaleTimeString())
    } catch (err) {
      setError(err.response?.data?.message ?? 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }, [showAllJobs])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, REFRESH_MS)
    return () => clearInterval(id)
  }, [fetchAll])

  const fmtMs = ms => {
    const n = Number(ms)
    if (ms == null || isNaN(n) || n <= 0) return '—'
    return n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${Math.round(n)}ms`
  }

  const hitRate = stats ? (stats.total > 0 ? Math.round((stats.cache_hits / stats.total) * 100) : 0) : 0

  const TABS = [
    { id: 'overview',   label: '📊 Overview'  },
    { id: 'analytics',  label: '🌍 Analytics' },
    { id: 'files',      label: '📁 Files'     },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Pipeline Dashboard</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Auto-refreshes every 30 s
            {lastSync && <> · Last sync: <span className="font-mono">{lastSync}</span></>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Tab nav */}
          <nav className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
                  activeTab === t.id ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                }`}>
                {t.label}
              </button>
            ))}
          </nav>
          <button onClick={() => { setLoading(true); fetchAll() }}
            className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition">
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">{error}</div>}

      {/* ── OVERVIEW TAB ── */}
      {activeTab === 'overview' && (
        <div className="space-y-8">
          {loading && !stats ? (
            <div className="text-center text-gray-400 py-12">Loading stats…</div>
          ) : stats && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                <StatCard label="Total Jobs"   value={stats.total}      color="indigo" />
                <StatCard label="Completed"    value={stats.completed}  color="green"  />
                <StatCard label="Failed"       value={stats.failed}     color="red"    />
                <StatCard label="Pending"      value={stats.pending}    color="yellow" />
                <StatCard label="Cache Hits"   value={stats.cache_hits} sub={`${hitRate}% hit rate`} color="purple" />
                <StatCard label="Avg Duration" value={fmtMs(stats.avg_duration_ms)} sub="per completed job" color="gray" />
              </div>

              {/* Mode breakdown + Stage timings */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="text-sm font-semibold text-gray-700 mb-4">Jobs by Output Mode</h3>
                  {Object.keys(stats.by_mode || {}).length === 0
                    ? <p className="text-sm text-gray-400">No data yet</p>
                    : (
                      <div className="space-y-3">
                        {Object.entries(stats.by_mode).map(([mode, count]) => {
                          const pct = stats.total > 0 ? Math.round((count / stats.total) * 100) : 0
                          const colors = { questions: 'bg-indigo-500', text: 'bg-green-500', both: 'bg-purple-500' }
                          return (
                            <div key={mode}>
                              <div className="flex justify-between text-sm mb-1">
                                <span className="font-medium text-gray-700 capitalize">{mode}</span>
                                <span className="text-gray-500">{count} ({pct}%)</span>
                              </div>
                              <div className="w-full bg-gray-100 rounded-full h-2">
                                <div className={`h-2 rounded-full ${colors[mode] ?? 'bg-gray-400'}`} style={{ width: `${pct}%` }} />
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )
                  }
                </div>

                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="text-sm font-semibold text-gray-700 mb-4">Avg Stage Duration</h3>
                  {Object.keys(stats.stage_avg_ms || {}).length === 0
                    ? <p className="text-sm text-gray-400">No stage data yet</p>
                    : (
                      <div className="space-y-2">
                        {Object.entries(stats.stage_avg_ms)
                          .sort((a, b) => b[1].avg_ms - a[1].avg_ms)
                          .map(([stage, info]) => (
                            <div key={stage} className="flex items-center justify-between text-sm">
                              <span className="text-gray-600 font-mono text-xs truncate w-48">{stage}</span>
                              <span className="font-semibold text-gray-800">{fmtMs(info.avg_ms)}</span>
                              <span className="text-gray-400 text-xs">{info.runs} runs</span>
                            </div>
                          ))
                        }
                      </div>
                    )
                  }
                </div>
              </div>

              {/* Cache banner */}
              {cache && (
                <div className={`flex items-center gap-3 p-4 rounded-lg border text-sm ${
                  cache.redis_connected ? 'bg-purple-50 border-purple-200 text-purple-800' : 'bg-blue-50 border-blue-200 text-blue-800'
                }`}>
                  <span className="text-lg">{cache.redis_connected ? '⚡' : '🧠'}</span>
                  <div>
                    <span className="font-semibold">{cache.redis_connected ? 'Redis + Memory cache active' : 'In-memory cache active'}</span>
                    <span className="ml-2 opacity-75">
                      {cache.redis_connected
                        ? `Repeated documents skip the full pipeline (TTL ${cache.cache_ttl_seconds / 3600}h)`
                        : 'Set REDIS_URL for persistent cache.'}
                    </span>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Recent jobs */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700">
                {showAllJobs ? 'All Jobs' : 'Last 3 Jobs'}
              </h3>
              <button onClick={() => setShowAllJobs(s => !s)}
                className="text-xs text-indigo-600 hover:underline">
                {showAllJobs ? 'Show less' : 'View all jobs →'}
              </button>
            </div>
            {jobs.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-10">No jobs yet</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <th className="px-4 py-3">Pipeline ID</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Questions</th>
                      <th className="px-4 py-3">Cache</th>
                      <th className="px-4 py-3">Duration</th>
                      <th className="px-4 py-3">Reason / Stage</th>
                      <th className="px-4 py-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {jobs.map(job => {
                      const isCached = !!job.cached
                      const dur      = fmtMs(job.duration_ms)
                      const created  = job.created_at ? new Date(job.created_at).toLocaleString() : '—'
                      const reasonStyle =
                        job.status === 'failed'     ? 'text-red-600' :
                        job.status === 'processing' ? 'text-blue-600 animate-pulse' :
                        job.status === 'queued'     ? 'text-yellow-600' :
                        isCached                    ? 'text-purple-600' : 'text-green-600'
                      return (
                        <tr key={job.pipeline_id}
                          className={`transition ${isCached && job.status === 'completed' ? 'bg-purple-50 hover:bg-purple-100' : 'hover:bg-gray-50'}`}>
                          <td className="px-4 py-3 font-mono text-xs text-gray-600">{job.pipeline_id}</td>
                          <td className="px-4 py-3"><StatusBadge status={job.status} /></td>
                          <td className="px-4 py-3 capitalize text-gray-700">{job.output_mode}</td>
                          <td className="px-4 py-3 text-gray-600">{job.num_questions}</td>
                          <td className="px-4 py-3"><CacheBadge cached={isCached} /></td>
                          <td className="px-4 py-3 font-mono text-xs">
                            {isCached ? <span className="text-purple-700 font-semibold">⚡ {dur}</span> : <span className="text-gray-600">{dur}</span>}
                          </td>
                          <td className={`px-4 py-3 text-xs ${reasonStyle}`}>{job.reason || '—'}</td>
                          <td className="px-4 py-3 text-gray-500 text-xs">{created}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Reviews & Ratings */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="text-base font-semibold text-gray-800 mb-1">Rate Your Experience</h3>
              <p className="text-xs text-gray-500 mb-4">Your feedback helps improve the service.</p>
              <ReviewForm onSubmitted={fetchAll} />
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
              <h3 className="text-base font-semibold text-gray-800">User Ratings</h3>
              {!revStats || revStats.total === 0 ? (
                <p className="text-sm text-gray-400">No reviews yet — be the first!</p>
              ) : (
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className="text-5xl font-bold text-gray-900">{revStats.avg_rating.toFixed(1)}</p>
                    <StarRating value={Math.round(revStats.avg_rating)} readonly />
                    <p className="text-xs text-gray-400 mt-1">{revStats.total} review{revStats.total !== 1 ? 's' : ''}</p>
                  </div>
                  <div className="flex-1 space-y-1.5">
                    {[5,4,3,2,1].map(s => <RatingBar key={s} star={s} count={revStats.distribution[s] ?? 0} total={revStats.total} />)}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Recent reviews with replies */}
          {reviews.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Recent Reviews</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {reviews.map(r => <ReviewCard key={r.review_id} review={r} onReplyPosted={fetchAll} />)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── ANALYTICS TAB ── */}
      {activeTab === 'analytics' && <AnalyticsSection />}

      {/* ── FILES TAB ── */}
      {activeTab === 'files' && <FilesSection onDeleted={fetchAll} />}
    </div>
  )
}
