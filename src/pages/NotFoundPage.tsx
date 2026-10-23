import { Compass } from 'lucide-react'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { ButtonLink } from '@/components/ui/Button'

export function NotFoundPage() {
  useDocumentTitle('Page not found')
  return (
    <div className="container-page flex min-h-[60vh] items-center py-16">
      <div className="mx-auto max-w-xl text-center">
        <p className="font-serif text-6xl italic leading-none text-gold-deep sm:text-7xl">404</p>
        <h1 className="mt-5 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          This page is not on the board.
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-muted">
          The link may be outdated, or the page moved. The weekly competition and the
          leaderboard are still exactly where you left them.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
          <ButtonLink to="/" icon={<Compass className="h-4 w-4" aria-hidden="true" />}>
            Back to home
          </ButtonLink>
          <ButtonLink to="/leaderboard" variant="secondary">
            View leaderboard
          </ButtonLink>
        </div>
      </div>
    </div>
  )
}
