import {
  AlertTriangle,
  CheckCircle2,
  Info,
  ShieldAlert,
  X,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/utils/cn'

type NoticeVariant = 'info' | 'success' | 'warning' | 'danger' | 'neutral'

const STYLES: Record<NoticeVariant, { wrapper: string; icon: string; Icon: LucideIcon }> = {
  info: {
    wrapper: 'border-forest/15 bg-forest-tint/60',
    icon: 'text-forest',
    Icon: Info,
  },
  success: {
    wrapper: 'border-success/20 bg-success/[0.06]',
    icon: 'text-success',
    Icon: CheckCircle2,
  },
  warning: {
    wrapper: 'border-warning/25 bg-warning/[0.07]',
    icon: 'text-warning',
    Icon: AlertTriangle,
  },
  danger: {
    wrapper: 'border-danger/20 bg-danger/[0.05]',
    icon: 'text-danger',
    Icon: ShieldAlert,
  },
  neutral: {
    wrapper: 'border-line bg-surface',
    icon: 'text-muted',
    Icon: Info,
  },
}

export function Notice({
  variant = 'info',
  title,
  children,
  action,
  onDismiss,
  className,
}: {
  variant?: NoticeVariant
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  onDismiss?: () => void
  className?: string
}) {
  const style = STYLES[variant]
  const Icon = style.Icon
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-card border p-4 sm:px-5',
        style.wrapper,
        className,
      )}
      role={variant === 'danger' ? 'alert' : 'note'}
    >
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', style.icon)} aria-hidden="true" />
      <div className="min-w-0 flex-1 text-sm leading-relaxed">
        {title ? <p className="font-semibold text-ink">{title}</p> : null}
        {children ? (
          <div className={cn('text-[0.8125rem] text-muted', title && 'mt-1')}>
            {children}
          </div>
        ) : null}
        {action ? <div className="mt-3">{action}</div> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss notice"
          className="rounded p-1 text-muted transition hover:bg-black/5 hover:text-ink"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  )
}
