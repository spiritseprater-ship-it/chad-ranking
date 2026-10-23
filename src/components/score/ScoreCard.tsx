import type { ReactNode } from 'react'
import type { ProvisionalScore, ScoreBreakdownItem } from '@/types/domain'
import { ENTERTAINMENT_DISCLAIMER } from '@/config/constants'
import { cn } from '@/utils/cn'
import { Info } from 'lucide-react'

export function ScoreBreakdown({
  breakdown,
  className,
}: {
  breakdown: ScoreBreakdownItem[]
  className?: string
}) {
  return (
    <dl className={cn('space-y-4', className)}>
      {breakdown.map((item) => (
        <div key={item.category}>
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-sm font-medium text-ink">
              {item.label}
              <span className="ml-2 text-[10px] font-normal uppercase tracking-wider text-muted">
                {Math.round(item.weight * 100)}%
              </span>
            </dt>
            <dd className="font-display text-sm font-semibold tabular-nums text-ink">
              {item.score}
            </dd>
          </div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
            <div
              className={cn(
                'h-full rounded-full',
                item.category === 'pose' ? 'bg-forest' : 'bg-forest/55',
              )}
              style={{ width: `${Math.max(2, item.score)}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{item.description}</p>
        </div>
      ))}
    </dl>
  )
}

export function ScoreCard({
  score,
  label = 'Provisional score',
  title,
  caption,
  breakdown,
  footer,
  className,
}: {
  score: number
  label?: string
  title?: string
  caption?: ReactNode
  breakdown?: ProvisionalScore['breakdown']
  footer?: ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        'overflow-hidden rounded-card border border-line bg-surface',
        className,
      )}
      aria-label={`${label}: ${score} out of 100`}
    >
      <div className="relative border-b border-line px-6 py-7 sm:px-8 sm:py-9">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">{label}</p>
            <p className="mt-4 flex items-baseline gap-2">
              <span className="font-display text-6xl font-semibold leading-none tracking-[-0.04em] text-ink tabular-nums sm:text-7xl">
                {score}
              </span>
              <span className="font-serif text-lg italic text-muted">/ 100</span>
            </p>
            <span className="gold-rule mt-5" aria-hidden="true" />
            {title ? (
              <p className="mt-4 font-display text-sm font-semibold uppercase tracking-[0.16em] text-gold-deep">
                {title}
              </p>
            ) : null}
          </div>
          {caption ? (
            <div className="max-w-xs text-xs leading-relaxed text-muted sm:text-right">
              {caption}
            </div>
          ) : null}
        </div>
      </div>
      {breakdown ? (
        <div className="px-6 py-6 sm:px-8 sm:py-7">
          <p className="eyebrow">Entertainment categories</p>
          <ScoreBreakdown breakdown={breakdown} className="mt-5" />
        </div>
      ) : null}
      {footer ? <div className="border-t border-line px-6 py-5 sm:px-8">{footer}</div> : null}
    </section>
  )
}

export function EntertainmentDisclaimer({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex items-start gap-2.5 rounded-lg border border-line bg-subtle/50 px-4 py-3',
        className,
      )}
    >
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
      <p className="text-[11px] leading-relaxed text-muted">{ENTERTAINMENT_DISCLAIMER}</p>
    </div>
  )
}
