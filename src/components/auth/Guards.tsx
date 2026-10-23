import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { LoadingState } from '@/components/ui/States'
import { ButtonLink } from '@/components/ui/Button'
import { BackendBanner } from '@/components/common/BackendBanner'

function FullPageLoading() {
  return (
    <div className="container-page py-24">
      <LoadingState label="Checking your session…" />
    </div>
  )
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <FullPageLoading />
  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }
  return <>{children}</>
}

export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  if (status === 'loading') return <FullPageLoading />
  if (user) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

/**
 * Admin access is enforced by the backend as well as this UI gate.
 * Unauthorized accounts see a clear access-denied screen, never a broken shell.
 */
export function AccessDenied() {
  return (
    <div className="container-page py-16 sm:py-24">
      <div className="mx-auto max-w-xl rounded-card border border-line bg-surface px-6 py-10 text-center sm:px-10">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-danger/10 text-danger">
          <ShieldAlert className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="eyebrow mt-6">Restricted area</p>
        <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight text-ink">
          Access denied
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-muted">
          This dashboard is limited to authorized administrators. Administrator
          access is granted by the project owner through a trusted process — it
          is never enabled by a URL, a username, or a setting in this browser.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
          <ButtonLink to="/dashboard" variant="primary" size="sm">
            Return to dashboard
          </ButtonLink>
          <ButtonLink to="/" variant="secondary" size="sm">
            Back to home
          </ButtonLink>
        </div>
        <BackendBanner className="mt-8 text-left" />
      </div>
    </div>
  )
}
