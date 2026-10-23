import type { ReactNode } from 'react'
import { cn } from '@/utils/cn'

type BadgeVariant =
  | 'neutral'
  | 'outline'
  | 'forest'
  | 'gold'
  | 'success'
  | 'warning'
  | 'danger'

const VARIANTS: Record<BadgeVariant, string> = {
  neutral: 'bg-subtle text-muted border-transparent',
  outline: 'bg-transparent text-muted border-line',
  forest: 'bg-forest-tint text-forest border-forest/15',
  gold: 'bg-gold-tint text-gold-deep border-gold/30',
  success: 'bg-success/10 text-success border-success/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  danger: 'bg-danger/10 text-danger border-danger/20',
}

export function Badge({
  children,
  variant = 'neutral',
  className,
  icon,
}: {
  children: ReactNode
  variant?: BadgeVariant
  className?: string
  icon?: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.625rem] font-semibold uppercase tracking-[0.12em] leading-none',
        VARIANTS[variant],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
