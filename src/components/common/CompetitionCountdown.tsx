import { useEffect, useRef } from 'react'
import { useCountdown } from '@/hooks/useCountdown'
import { padTime } from '@/utils/datetime'
import { cn } from '@/utils/cn'

function Segment({
  value,
  label,
  tone,
}: {
  value: string
  label: string
  tone: 'light' | 'dark'
}) {
  return (
    <div className="flex flex-col items-center">
      <span
        className={cn(
          'font-display text-2xl font-semibold tabular-nums leading-none tracking-tight sm:text-[1.75rem]',
          tone === 'dark' ? 'text-canvas' : 'text-ink',
        )}
      >
        {value}
      </span>
      <span
        className={cn(
          'mt-1.5 text-[0.5625rem] font-semibold uppercase tracking-[0.16em]',
          tone === 'dark' ? 'text-canvas/70' : 'text-muted',
        )}
      >
        {label}
      </span>
    </div>
  )
}

/**
 * Counts down to the competition's server-provided end timestamp.
 * Never uses a hardcoded deadline.
 */
export function CompetitionCountdown({
  endsAt,
  offsetMs = 0,
  tone = 'light',
  label = 'Competition ends in',
  onExpire,
  eyebrow,
  className,
}: {
  endsAt: string
  offsetMs?: number
  tone?: 'light' | 'dark'
  label?: string
  onExpire?: () => void
  eyebrow?: string
  className?: string
}) {
  const countdown = useCountdown(endsAt, offsetMs)
  const notified = useRef(false)

  useEffect(() => {
    if (!countdown?.expired) {
      notified.current = false
      return
    }
    if (notified.current) return
    notified.current = true
    onExpire?.()
  }, [countdown?.expired, onExpire])

  if (!countdown) return null

  if (countdown.expired) {
    return (
      <div className={cn('text-left', className)} role="status">
        <p
          className={cn(
            'eyebrow',
            tone === 'dark' && 'text-canvas/70',
          )}
        >
          {eyebrow ?? 'This week'}
        </p>
        <p
          className={cn(
            'mt-2 font-display text-lg font-semibold',
            tone === 'dark' ? 'text-canvas' : 'text-ink',
          )}
        >
          The week has closed.
        </p>
        <p
          className={cn(
            'mt-1 max-w-xs text-xs leading-relaxed',
            tone === 'dark' ? 'text-canvas/70' : 'text-muted',
          )}
        >
          The next competition opens Monday at 00:00 IST. The official state is
          confirmed by the backend, not by this countdown.
        </p>
      </div>
    )
  }

  return (
    <div className={className} role="timer" aria-label={`${label}: ${countdown.days} days, ${countdown.hours} hours, ${countdown.minutes} minutes`}>
      <div className="flex items-center gap-2">
        {eyebrow ? (
          <p className={cn('eyebrow', tone === 'dark' && 'text-canvas/70')}>{eyebrow}</p>
        ) : null}
      </div>
      <p
        className={cn(
          'text-[0.625rem] font-semibold uppercase tracking-[0.16em]',
          tone === 'dark' ? 'text-canvas/70' : 'text-muted',
          eyebrow && 'mt-2',
        )}
      >
        {label}
      </p>
      <div className="mt-3 flex items-start gap-3 sm:gap-4">
        <Segment value={String(countdown.days).padStart(2, '0')} label="days" tone={tone} />
        <span className={cn('pt-0.5 font-display text-xl', tone === 'dark' ? 'text-canvas/25' : 'text-line')}>:</span>
        <Segment value={padTime(countdown.hours)} label="hours" tone={tone} />
        <span className={cn('pt-0.5 font-display text-xl', tone === 'dark' ? 'text-canvas/25' : 'text-line')}>:</span>
        <Segment value={padTime(countdown.minutes)} label="mins" tone={tone} />
        <span className={cn('hidden pt-0.5 font-display text-xl sm:block', tone === 'dark' ? 'text-canvas/25' : 'text-line')}>:</span>
        <div className="hidden sm:block">
          <Segment value={padTime(countdown.seconds)} label="secs" tone={tone} />
        </div>
      </div>
    </div>
  )
}
