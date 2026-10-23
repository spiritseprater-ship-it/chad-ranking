import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Wordmark } from '@/components/layout/Logo'

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  aside,
  footer,
}: {
  eyebrow: string
  title: string
  description?: ReactNode
  children: ReactNode
  aside?: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-canvas">
      <div className="container-page py-10 sm:py-14 lg:py-16">
        <div className={aside ? 'grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-16' : 'mx-auto max-w-md'}>
          <div className="mx-auto w-full max-w-md lg:mx-0">
            <Link to="/" className="inline-block lg:hidden">
              <Wordmark />
            </Link>
            <p className="eyebrow mt-8 lg:mt-0">{eyebrow}</p>
            <h1 className="mt-3 font-display text-3xl font-semibold tracking-[-0.02em] text-ink sm:text-[2.15rem]">
              {title}
            </h1>
            {description ? (
              <div className="mt-3 text-sm leading-relaxed text-muted">{description}</div>
            ) : null}
            <div className="mt-8">{children}</div>
            {footer ? <div className="mt-6 text-sm text-muted">{footer}</div> : null}
          </div>

          {aside ? (
            <aside className="lg:pt-14">
              <div className="overflow-hidden rounded-card border border-line bg-surface">
                <div className="h-px bg-gradient-to-r from-gold/60 via-gold/20 to-transparent" />
                <div className="p-6">{aside}</div>
              </div>
            </aside>
          ) : null}
        </div>
      </div>
    </div>
  )
}
