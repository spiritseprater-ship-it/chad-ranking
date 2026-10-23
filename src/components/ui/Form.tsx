import { useId, useState, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { cn } from '@/utils/cn'

const FIELD_CLASSES =
  'w-full rounded-field border border-line bg-surface px-3.5 py-2.5 text-sm text-ink shadow-none transition placeholder:text-muted hover:border-line focus:border-forest focus:outline-none focus:ring-2 focus:ring-forest/15 disabled:cursor-not-allowed disabled:bg-subtle'

export function Field({
  id,
  label,
  hint,
  error,
  required,
  optional,
  children,
  className,
}: {
  id: string
  label: string
  hint?: ReactNode
  error?: string
  required?: boolean
  optional?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
          {required ? (
            <span className="ml-1 text-danger" aria-hidden="true">
              *
            </span>
          ) : null}
          {optional ? (
            <span className="ml-1.5 text-xs font-normal text-muted">(optional)</span>
          ) : null}
        </label>
      </div>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-xs font-medium text-danger" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs leading-relaxed text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export function TextInput({ className, invalid, ...rest }: TextInputProps) {
  return (
    <input
      className={cn(FIELD_CLASSES, invalid && 'border-danger focus:border-danger focus:ring-danger/15', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  )
}

export function PasswordInput({
  invalid,
  className,
  ...rest
}: TextInputProps) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        className={cn(FIELD_CLASSES, 'pr-11', invalid && 'border-danger focus:border-danger focus:ring-danger/15', className)}
        aria-invalid={invalid || undefined}
        {...rest}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-field text-muted transition hover:text-ink"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? (
          <EyeOff className="h-4 w-4" aria-hidden="true" />
        ) : (
          <Eye className="h-4 w-4" aria-hidden="true" />
        )}
      </button>
    </div>
  )
}

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean
}

export function TextArea({ className, invalid, ...rest }: TextAreaProps) {
  return (
    <textarea
      className={cn(FIELD_CLASSES, 'min-h-24 resize-y leading-relaxed', invalid && 'border-danger focus:border-danger focus:ring-danger/15', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  )
}

export function Select({
  className,
  children,
  invalid,
  ...rest
}: React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      className={cn(FIELD_CLASSES, 'h-11 cursor-pointer py-0', invalid && 'border-danger', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    >
      {children}
    </select>
  )
}

export function Checkbox({
  id,
  label,
  error,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { id: string; label: ReactNode; error?: string }) {
  return (
    <div>
      <div className="flex items-start gap-3">
        <input
          id={id}
          type="checkbox"
          className="mt-0.5 h-4 w-4 shrink-0 accent-forest"
          {...rest}
        />
        <label htmlFor={id} className="text-xs leading-relaxed text-muted">
          {label}
        </label>
      </div>
      {error ? (
        <p className="mt-1 text-xs font-medium text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

/** Password strength hint, used only on registration. */
export function PasswordStrength({ score, label }: { score: number; label: string }) {
  return (
    <div className="flex items-center gap-2" aria-live="polite">
      <div className="flex flex-1 gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className={cn(
              'h-1 flex-1 rounded-full bg-line transition-colors',
              index < score && (score === 3 ? 'bg-success' : score === 2 ? 'bg-warning' : 'bg-danger'),
            )}
          />
        ))}
      </div>
      <span className="w-16 text-right text-[11px] text-muted">{label}</span>
    </div>
  )
}

/** Generates stable ids for form sections. */
export function useFieldId(prefix: string): string {
  const id = useId()
  return `${prefix}-${id.replace(/:/g, '')}`
}
