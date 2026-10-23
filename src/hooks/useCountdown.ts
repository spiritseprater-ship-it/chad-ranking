import { useEffect, useMemo, useState } from 'react'
import { getCountdownParts, type CountdownParts } from '@/utils/datetime'

/**
 * Ticks once per second against the competition's authoritative `endsAt`.
 *
 * Phase 2 will periodically refetch competition state so the countdown does
 * not rely solely on the device clock; the server timestamp is the source of
 * truth for the window itself.
 */
export function useCountdown(
  endsAt: string | null,
  offsetMs = 0,
): CountdownParts | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!endsAt) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [endsAt])

  return useMemo(
    () => (endsAt ? getCountdownParts(endsAt, now + offsetMs) : null),
    [endsAt, now, offsetMs],
  )
}
