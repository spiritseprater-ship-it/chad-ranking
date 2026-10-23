import { Link } from 'react-router-dom'
import { FlaskConical, PlugZap, ServerOff } from 'lucide-react'
import { backendMode } from '@/services'
import { cn } from '@/utils/cn'

/**
 * Explicit, honest environment labels. The app never presents demo or
 * unconfigured states as a working production backend.
 */
export function PreviewStrip() {
  if (backendMode !== 'demo') return null
  return (
    <div className="bg-forest-900 text-canvas">
      <div className="container-page flex items-center justify-center gap-2 py-1.5 text-center">
        <FlaskConical className="h-3 w-3 text-gold" aria-hidden="true" />
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-canvas/75">
          Frontend preview · sample data · not connected to Firebase
        </p>
      </div>
    </div>
  )
}

const COPY = {
  demo: {
    icon: FlaskConical,
    title: 'This is a design preview, not live data.',
    body: 'Accounts, scores and moderation actions are kept in this browser tab and disappear on reload. Firebase integration arrives in Phase 2.',
    tone: 'border-gold/30 bg-gold-tint/60',
  },
  unconfigured: {
    icon: ServerOff,
    title: 'Backend not configured in this build.',
    body: 'The interface is ready, but authentication, rankings and moderation need Firebase. Follow the setup steps in the README and docs/FIREBASE_PLAN.md.',
    tone: 'border-warning/25 bg-warning/[0.06]',
  },
  firebase: {
    icon: PlugZap,
    title: 'Firebase configuration detected.',
    body: 'The Firebase service layer is scheduled for Phase 2. Until then, data screens fail safely instead of inventing results.',
    tone: 'border-forest/20 bg-forest-tint/60',
  },
} as const

export function BackendBanner({ className }: { className?: string }) {
  const copy = COPY[backendMode]
  const Icon = copy.icon
  return (
    <div className={cn('rounded-card border px-4 py-3.5 sm:px-5', copy.tone, className)}>
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink/60" aria-hidden="true" />
        <div className="text-[0.8125rem] leading-relaxed">
          <p className="font-semibold text-ink">{copy.title}</p>
          <p className="mt-0.5 text-muted">
            {copy.body}{' '}
            <Link to="/rules#data-status" className="font-medium text-forest underline underline-offset-2">
              Data status
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

/** Compact inline label used inside cards that show sample content. */
export function SampleDataTag({ label = 'Sample data' }: { label?: string }) {
  if (backendMode !== 'demo') return null
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-gold/30 bg-gold-tint px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-gold-deep">
      {label}
    </span>
  )
}
