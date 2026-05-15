import { useState, useEffect } from 'react'

/**
 * RateLimitBanner
 * ────────────────
 * Displays a countdown when the user hits the 10-req/hr rate limit.
 * Disappears automatically when the countdown reaches zero.
 */
export default function RateLimitBanner({ retryAfter, debugId, onExpired }) {
  const [remaining, setRemaining] = useState(retryAfter ?? 0)

  useEffect(() => {
    setRemaining(retryAfter ?? 0)
  }, [retryAfter])

  useEffect(() => {
    if (remaining <= 0) {
      onExpired?.()
      return
    }
    const timer = setInterval(() => {
      setRemaining((s) => {
        if (s <= 1) { onExpired?.(); return 0 }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [remaining, onExpired])

  if (!remaining) return null

  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60

  return (
    <div className="mt-4 p-4 bg-amber-50 border border-amber-300 rounded-md">
      <div className="flex items-start gap-3">
        <span className="text-amber-500 text-xl">⏳</span>
        <div>
          <p className="font-semibold text-amber-800">Hourly limit reached</p>
          <p className="text-amber-700 text-sm mt-1">
            You've used all 10 requests this hour. Available again in{' '}
            <span className="font-mono font-bold text-amber-900">
              {mins}:{String(secs).padStart(2, '0')}
            </span>
          </p>
          {debugId && (
            <p className="text-amber-500 text-xs mt-2 font-mono">
              ref: {debugId}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
