import { Link } from 'react-router-dom'
import { cn } from '@/utils/cn'

export function Logo({
  className,
  compact = false,
}: {
  className?: string
  compact?: boolean
}) {
  return (
    <Link
      to="/"
      className={cn('group inline-flex items-center gap-2.5', className)}
      aria-label="CHAD RANKING home"
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] bg-forest font-serif text-base font-semibold text-canvas ring-1 ring-inset ring-gold/40">
        C
      </span>
      <span className="flex flex-col leading-none">
        <span className="font-display text-[0.9375rem] font-bold tracking-[0.04em] text-ink">
          CHAD
        </span>
        <span
          className={cn(
            'mt-0.5 font-display text-[0.5625rem] font-medium tracking-[0.32em] text-muted',
            compact && 'hidden sm:block',
          )}
        >
          RANKING
        </span>
      </span>
    </Link>
  )
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-forest font-serif text-lg font-semibold text-canvas ring-1 ring-inset ring-gold/40">
        C
      </span>
      <span>
        <span className="block font-display text-sm font-bold tracking-[0.05em] text-ink">
          CHAD RANKING
        </span>
        <span className="mt-1 block text-[9px] font-medium uppercase tracking-[0.2em] text-muted">
          The ranking is yours to claim
        </span>
      </span>
    </div>
  )
}
