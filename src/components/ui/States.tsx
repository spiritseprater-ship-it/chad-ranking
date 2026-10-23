import { AlertTriangle, Inbox, Loader2, RefreshCw, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/utils/cn'
import { Button } from './Button'

export function Spinner({ className }: { className?: string }) {
  return (
    <Loader2
      className={cn('h-4 w-4 animate-spin text-forest', className)}
      aria-hidden="true"
    />
  )
}

export function LoadingState({
  label = 'Loading…',
  className,
}: {
  label?: string
  className?: string
}) {
  return (
    <div
      className={cn('flex items-center justify-center gap-3 py-16', className)}
      role="status"
      aria-live="polite"
    >
      <Spinner className="h-5 w-5" />
      <span className="text-sm text-muted">{label}</span>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
  className,
}: {
  title: string
  description?: ReactNode
  action?: ReactNode
  icon?: LucideIcon
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center rounded-card border border-dashed border-line bg-surface/60 px-6 py-14 text-center',
        className,
      )}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-subtle text-muted">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <h3 className="mt-4 font-display text-lg font-semibold tracking-tight text-ink">
        {title}
      </h3>
      {description ? (
        <div className="mt-2 max-w-md text-sm leading-relaxed text-muted">
          {description}
        </div>
      ) : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  )
}

export function ErrorState({
  title = 'Something went wrong',
  message,
  code,
  onRetry,
  retryLabel = 'Try again',
  className,
}: {
  title?: string
  message: string
  code?: string
  onRetry?: () => void
  retryLabel?: string
  className?: string
}) {
  return (
    <div
      role="alert"
      className={cn(
        'rounded-card border border-danger/20 bg-surface px-6 py-10 text-center sm:px-10',
        className,
      )}
    >
      <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
      </span>
      <h3 className="mt-4 font-display text-lg font-semibold text-ink">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-muted">
        {message}
      </p>
      {code ? (
        <p className="mt-3 font-mono text-[10px] uppercase tracking-widest text-muted">
          Reference: {code}
        </p>
      ) : null}
      {onRetry ? (
        <Button
          variant="secondary"
          size="sm"
          className="mt-6"
          onClick={onRetry}
          icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}
        >
          {retryLabel}
        </Button>
      ) : null}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-subtle', className)}
      aria-hidden="true"
    />
  )
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading table">
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 rounded-lg border border-line bg-surface px-4 py-3.5"
        >
          <Skeleton className="h-8 w-8 rounded-full" />
          <Skeleton className="h-3.5 w-32" />
          <Skeleton className="ml-auto h-3.5 w-12" />
        </div>
      ))}
    </div>
  )
}
