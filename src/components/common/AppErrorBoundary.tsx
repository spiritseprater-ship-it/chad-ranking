import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  reference: string | null
}

/**
 * Catches unexpected render errors and shows a safe, non-technical fallback.
 * Raw stacks are logged to the console only, never rendered to the participant.
 */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, reference: null }

  static getDerivedStateFromError(): State {
    return {
      hasError: true,
      reference: `ui-${Date.now().toString(36).slice(-6)}`,
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Keep diagnostics local; do not send personal data to third parties.
    console.error('Unhandled UI error', error, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-6 py-16">
        <div className="w-full max-w-md rounded-card border border-line bg-surface p-8 text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-danger/10 text-danger">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </span>
          <h1 className="mt-5 font-display text-xl font-semibold text-ink">
            The page hit an unexpected error.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Your account and confirmed scores are not affected by a display error. Reload
            the page to continue. If it keeps happening, share the reference below with
            an administrator — never share your password.
          </p>
          {this.state.reference ? (
            <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-muted">
              Reference {this.state.reference}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-6 inline-flex h-10 items-center gap-2 rounded-field bg-forest px-4 text-[11px] font-semibold uppercase tracking-[0.08em] text-white transition hover:bg-forest-700"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Reload page
          </button>
        </div>
      </div>
    )
  }
}
