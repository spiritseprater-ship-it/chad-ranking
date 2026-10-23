import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/utils/cn'

export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'danger'
  | 'gold'
  | 'inverse'
export type ButtonSize = 'sm' | 'md' | 'lg'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-field font-semibold uppercase tracking-[0.08em] transition-colors transition-transform duration-150 disabled:pointer-events-none disabled:opacity-45 active:translate-y-px'

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-forest text-white hover:bg-forest-700 shadow-soft focus-visible:outline-forest',
  secondary:
    'border border-line bg-surface text-ink hover:border-forest/30 hover:bg-forest-tint/50',
  ghost: 'text-ink hover:bg-subtle',
  danger: 'bg-danger text-white hover:bg-danger/90',
  gold: 'bg-gold text-forest-900 hover:bg-gold-deep hover:text-white',
  inverse:
    'bg-canvas text-forest-900 hover:bg-white focus-visible:outline-white',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3.5 text-[0.6875rem]',
  md: 'h-11 px-5 text-[0.75rem]',
  lg: 'h-12 px-6 text-[0.8125rem]',
}

export function buttonClasses(options: {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  className?: string
} = {}): string {
  const { variant = 'primary', size = 'md', fullWidth, className } = options
  return cn(BASE, VARIANTS[variant], SIZES[size], fullWidth && 'w-full', className)
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  loading?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  fullWidth,
  loading,
  icon,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClasses({ variant, size, fullWidth, className })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        icon
      )}
      {children}
    </button>
  )
}

export function ButtonLink({
  to,
  variant = 'primary',
  size = 'md',
  fullWidth,
  className,
  icon,
  children,
}: {
  to: string
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  className?: string
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      className={buttonClasses({ variant, size, fullWidth, className })}
    >
      {icon}
      {children}
    </Link>
  )
}
