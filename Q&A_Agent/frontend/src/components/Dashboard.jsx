import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const REFRESH_MS = 30_000

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

function StarRating({ value, onChange, readonly = false }) {
  const [hover, setHover] = useState(0)
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={readonly}
          onClick={() => !readonly && onChange && onChange(star)}
          onMouseEnter={() => !readonly && setHover(star)}
          onMouseLeave={() => !readonly && setHover(0)}
          className={`text-2xl transition-transform ${readonly ? 'cursor-default' : 'cursor-pointer hover:scale-110'}`}
          aria-label={`${star} star`}
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

const USE_CASES = [
  '', 'Education / Study', 'Interview Prep', 'Quiz Creation',
  'Research', 'Corporate Training', 'Content Creation', 'Other',
]

function ReviewForm({ onSubmitted }) {
  const [rating,        setRating]        = useState(0)
  const [text,          setText]          = useState('')
  const [useCase,       setUseCase]       = useState('')
  const [reviewerName,  setReviewerName]  = useState('')
  const [submitting,    setSubmitting]    = useState(false)
  const [done,          setDone]          = useState(false)
  const [err,           setErr]           = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!rating) { setErr('Please select a star rating.'); return }
    setSubmitting(true)
    setErr('')
    try {
      await axios.post('/api/reviews', {
        rating,
        review_text:   text,
        use_case:      useCase,
        reviewer_name: reviewerName.trim(),
      })
      setDone(true)
      onSubmitted?.()
    } catch {
      setErr('Failed to submit — please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="text-center py-6">
        <div className="text-4xl mb-2">🎉</div>
        <p className="font-semibold text-green-700">Thank you for your feedback!</p>
        <p className="text-sm text-gray-500 mt-1">Your review helps improve the service.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Your Name <span className="text-gray-400 font-normal">(optional)</span>
        </label>
        <input
          type="text"
          value={reviewerName}
          onChange={(e) => setReviewerName(e.target.value)}
          maxLength={80}
          placeholder="e.g. Alice or @alice"
          className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Your Rating</label>
        <StarRating value={rating} onChange={setRating} />
        {rating > 0 && (
          <p className="text-xs text-gray-500 mt-1">
            {['','Poor','Fair','Good','Very Good','Excellent'][rating]}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Use Case (optional)</label>
        <select
          value={useCase}
          onChange={(e) => setUseCase(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        >
          {USE_CASES.map((u) => <option key={u} value={u}>{u || '— Select —'}</option>)}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Review (optional)</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={2000}
          rows={3}
          placeholder="What did you use it for? What worked well? What could be better?"
          className="w-full text-sm border border-gray-300 rounded-md px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
        <p className="text-xs text-gray-400 text-right">{text.length}/2000</p>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2 px-4 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 transition"
      >
        {submitting ? 'Submitting…' : 'Submit Review'}
      </button>
    </form>
  )
}

function ReviewCard({ review }) {
  const date = review.created_at ? new Date(review.created_at).toLocaleDateString() : '—'
  const sentimentColor = {
    positive: 'text-green-600',
    neutral:  'text-gray-500',
    negative: 'text-red-500',
  }[review.sentiment] ?? 'text-gray-400'

  const initials = review.reviewer_name
    ? review.reviewer_name.trim().split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0, 2)
    : '?'

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
      {/* Header: avatar + name + date */}
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
        <StarRating value={review.rating} readonly />
      </div>

      {review.use_case && (
        <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium">
          {review.use_case}
        </span>
      )}
      {review.review_text && (
        <p className="text-sm text-gray-700 leading-relaxed">{review.review_text}</p>
      )}
      {review.sentiment && (
        <p className={`text-xs font-medium ${sentimentColor}`}>
          Sentiment: {review.sentiment}
          {review.sentiment_score != null && ` (${review.sentiment_score.toFixed(2)})`}
        </p>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [stats,    setStats]    = useState(null)
  const [jobs,     setJobs]     = useState([])
  const [cache,    setCache]    = useState(null)
  const [reviews,  setReviews]  = useState([])
  const [revStats, setRevStats] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)
  const [lastSync, setLastSync] = useState(null)

  const fetchAll = useCallback(async () => {
    try {
      const [sRes, jRes, cRes, rRes] = await Promise.all([
        axios.get('/api/dashboard/stats'),
        axios.get('/api/dashboard/jobs?limit=20'),
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
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, REFRESH_MS)
    return () => clearInterval(id)
  }, [fetchAll])

  const fmtMs = (ms) => {
    const n = Number(ms)
    if (ms == null || isNaN(n) || n < 0) return '—'
    if (n === 0) return '—'
    return n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${Math.round(n)}ms`
  }
  const hitRate = stats ? (stats.total > 0 ? Math.round((stats.cache_hits / stats.total) * 100) : 0) : 0

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Pipeline Dashboard</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Auto-refreshes every 30 s
            {lastSync && <> · Last sync: <span className="font-mono">{lastSync}</span></>}
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); fetchAll() }}
          className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">{error}</div>
      )}

      {/* Summary cards */}
      {loading && !stats ? (
        <div className="text-center text-gray-400 py-12">Loading stats…</div>
      ) : stats && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard label="Total Jobs"   value={stats.total}     color="indigo" />
            <StatCard label="Completed"    value={stats.completed} color="green"  />
            <StatCard label="Failed"       value={stats.failed}    color="red"    />
            <StatCard label="Pending"      value={stats.pending}   color="yellow" />
            <StatCard label="Cache Hits"   value={stats.cache_hits}
                      sub={`${hitRate}% hit rate`}                 color="purple" />
            <StatCard label="Avg Duration" value={fmtMs(stats.avg_duration_ms)}
                      sub="per completed job"                       color="gray"   />
          </div>

          {/* Two-column: Mode breakdown + Stage timings */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Output mode breakdown */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">Jobs by Output Mode</h3>
              {Object.keys(stats.by_mode).length === 0
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
                            <div className={`h-2 rounded-full ${colors[mode] ?? 'bg-gray-400'}`}
                                 style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              }
            </div>

            {/* Stage timings */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-4">Avg Stage Duration</h3>
              {Object.keys(stats.stage_avg_ms).length === 0
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

          {/* Cache status banner */}
          {cache && (
            <div className={`flex items-center gap-3 p-4 rounded-lg border text-sm ${
              cache.redis_connected
                ? 'bg-purple-50 border-purple-200 text-purple-800'
                : 'bg-blue-50 border-blue-200 text-blue-800'
            }`}>
              <span className="text-lg">{cache.redis_connected ? '⚡' : '🧠'}</span>
              <div>
                <span className="font-semibold">
                  {cache.redis_connected ? 'Redis + Memory cache active' : 'In-memory cache active'}
                </span>
                <span className="ml-2 opacity-75">
                  {cache.redis_connected
                    ? `Repeated documents skip the full pipeline (TTL ${cache.cache_ttl_seconds / 3600}h)`
                    : 'Repeated documents served instantly within this session. Set REDIS_URL for persistent cache.'}
                </span>
              </div>
            </div>
          )}
        </>
      )}

      {/* Recent jobs table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-700">Recent Jobs (last 20)</h3>
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
                  <th className="px-4 py-3">Mode</th>
                  <th className="px-4 py-3">Questions</th>
                  <th className="px-4 py-3">Cache</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Reason / Stage</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {jobs.map((job) => {
                  const isCached = !!job.cached
                  const dur      = fmtMs(job.duration_ms)
                  const created  = job.created_at ? new Date(job.created_at).toLocaleString() : '—'

                  const reasonStyle =
                    job.status === 'failed'     ? 'text-red-600' :
                    job.status === 'processing' ? 'text-blue-600 animate-pulse' :
                    job.status === 'queued'     ? 'text-yellow-600' :
                    isCached                    ? 'text-purple-600' :
                                                  'text-green-600'

                  return (
                    <tr key={job.pipeline_id}
                        className={`transition ${isCached && job.status === 'completed' ? 'bg-purple-50 hover:bg-purple-100' : 'hover:bg-gray-50'}`}>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">{job.pipeline_id}</td>
                      <td className="px-4 py-3"><StatusBadge status={job.status} /></td>
                      <td className="px-4 py-3 capitalize text-gray-700">{job.output_mode}</td>
                      <td className="px-4 py-3 text-gray-600">{job.num_questions}</td>
                      <td className="px-4 py-3"><CacheBadge cached={isCached} /></td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {isCached
                          ? <span className="text-purple-700 font-semibold">⚡ {dur}</span>
                          : <span className="text-gray-600">{dur}</span>}
                      </td>
                      <td className={`px-4 py-3 text-xs ${reasonStyle}`}>
                        {job.reason || '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{created}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Reviews & Ratings ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Submit review */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-base font-semibold text-gray-800 mb-1">Rate Your Experience</h3>
          <p className="text-xs text-gray-500 mb-4">
            Your feedback is stored for quality analysis and future ML sentiment modelling.
          </p>
          <ReviewForm onSubmitted={fetchAll} />
        </div>

        {/* Aggregate stats */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
          <h3 className="text-base font-semibold text-gray-800">User Ratings</h3>

          {!revStats || revStats.total === 0 ? (
            <p className="text-sm text-gray-400">No reviews yet — be the first!</p>
          ) : (
            <>
              {/* Overall score */}
              <div className="flex items-center gap-4">
                <div className="text-center">
                  <p className="text-5xl font-bold text-gray-900">{revStats.avg_rating.toFixed(1)}</p>
                  <StarRating value={Math.round(revStats.avg_rating)} readonly />
                  <p className="text-xs text-gray-400 mt-1">{revStats.total} review{revStats.total !== 1 ? 's' : ''}</p>
                </div>
                <div className="flex-1 space-y-1.5">
                  {[5, 4, 3, 2, 1].map((s) => (
                    <RatingBar key={s} star={s} count={revStats.distribution[s] ?? 0} total={revStats.total} />
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Recent reviews list */}
      {reviews.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Recent Reviews</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {reviews.map((r) => <ReviewCard key={r.review_id} review={r} />)}
          </div>
        </div>
      )}

    </div>
  )
}
