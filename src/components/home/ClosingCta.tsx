import { ButtonLink } from '@/components/ui/Button'

export function ClosingCta({ signedIn }: { signedIn: boolean }) {
  return (
    <section className="border-t border-line bg-surface">
      <div className="container-page py-14 sm:py-16">
        <div className="flex flex-col items-start justify-between gap-7 rounded-card border border-line bg-canvas px-6 py-9 sm:px-10 lg:flex-row lg:items-center">
          <div>
            <p className="eyebrow">Enter · Compete · Claim your rank</p>
            <h2 className="mt-3 max-w-2xl font-display text-2xl font-semibold leading-tight tracking-[-0.015em] text-ink sm:text-[2rem]">
              The ranking is yours to claim.
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
              Free to join. Three photos. One confirmed score each week.
            </p>
          </div>
          <div className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:flex-row">
            <ButtonLink to={signedIn ? '/submit' : '/signup'} size="lg">
              {signedIn ? 'Enter this week' : 'Start competing'}
            </ButtonLink>
            <ButtonLink to="/leaderboard" variant="secondary" size="lg">
              View leaderboard
            </ButtonLink>
          </div>
        </div>
      </div>
    </section>
  )
}
