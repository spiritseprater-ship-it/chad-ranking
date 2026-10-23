import type { LucideIcon } from 'lucide-react'
import { cn } from '@/utils/cn'

export function AdminStatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'neutral',
}: {
  label: string
  value: number | string
  hint?: string
  icon: LucideIcon
  tone?: 'neutral' | 'gold' | 'danger' | 'forest'
}) {
  const toneClasses = {
    neutral: 'bg-subtle text-muted',
    gold: 'bg-gold-tint text-gold-deep',
    danger: 'bg-danger/10 text-danger',
    forest: 'bg-forest-tint text-forest',
  } as const

  return (
    <div className="rounded-card border border-line bg-surface p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[9px] font-semibold uppercase leading-relaxed tracking-[0.14em] text-muted">
          {label}
        </p>
        <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-md', toneClasses[tone])}>
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-3 font-display text-2xl font-semibold tabular-nums tracking-tight text-ink">
        {value}
      </p>
      {hint ? <p className="mt-1 text-[10px] leading-relaxed text-muted">{hint}</p> : null}
    </div>
  )
}
