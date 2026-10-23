import type { ReactNode } from 'react'
import { cn } from '@/utils/cn'

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <header className={cn('border-b border-line bg-canvas', className)}>
      <div className="container-page py-10 sm:py-14">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div className="min-w-0">
            {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
            <h1 className="mt-3 max-w-3xl font-display text-[1.75rem] font-semibold leading-[1.1] tracking-[-0.02em] text-ink sm:text-4xl lg:text-[2.75rem]">
              {title}
            </h1>
            {description ? (
              <div className="mt-3 max-w-2xl text-sm leading-relaxed text-muted sm:text-[0.9375rem]">
                {description}
              </div>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
        </div>
      </div>
    </header>
  )
}

export function SectionHeading({
  index,
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  index?: string
  eyebrow?: string
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col justify-between gap-5 sm:flex-row sm:items-end',
        className,
      )}
    >
      <div className="max-w-2xl">
        <div className="flex items-center gap-3">
          {index ? (
            <span className="font-serif text-sm italic text-gold-deep">{index}</span>
          ) : null}
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        </div>
        <h2 className="mt-3 font-display text-[1.625rem] font-semibold leading-tight tracking-[-0.015em] text-ink sm:text-3xl">
          {title}
        </h2>
        {description ? (
          <div className="mt-3 text-sm leading-relaxed text-muted sm:text-[0.9375rem]">
            {description}
          </div>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}
