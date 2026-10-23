import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { APP_SUBTAGLINE, ENTERTAINMENT_DISCLAIMER } from '@/config/constants'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { backendMode, services } from '@/services'
import { BackendBanner } from '@/components/common/BackendBanner'
import { ButtonLink } from '@/components/ui/Button'
import { HeroBoard } from '@/components/home/HeroBoard'
import { HowItWorks } from '@/components/home/HowItWorks'
import { WeekPanel } from '@/components/home/WeekPanel'
import { TopTenPreview } from '@/components/home/TopTenPreview'
import { RulesSummary } from '@/components/home/RulesSummary'
import { ClosingCta } from '@/components/home/ClosingCta'

const FACTS = [
  { value: '100', label: 'Ranked positions', detail: 'The official weekly leaderboard' },
  { value: '10', label: 'Showcase places', detail: 'An exclusive public profile' },
  { value: '01', label: 'Reset each week', detail: 'Monday · 00:00 IST' },
]

export function HomePage() {
  useDocumentTitle()
  const { user, status } = useAuth()
  const leaderboard = useAsync(() => services.leaderboard.getLeaderboard(), [])
  const entries = leaderboard.data?.ranked ?? []
  const unavailable = Boolean(leaderboard.error)
  const signedIn = Boolean(user)

  return (
    <>
      <section className="relative overflow-hidden border-b border-line">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 right-0 hidden w-[46%] bg-[linear-gradient(to_right,transparent,var(--color-subtle)_75%)] opacity-60 lg:block"
        />
        <div className="container-page relative py-12 sm:py-16 lg:py-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.08fr_0.92fr] lg:gap-16">
            <div>
              <div className="flex items-center gap-3">
                <span className="gold-rule" aria-hidden="true" />
                <p className="eyebrow">Weekly community competition</p>
              </div>

              <h1 className="mt-5 font-display text-[2.7rem] font-semibold leading-[0.98] tracking-[-0.035em] text-ink sm:text-6xl lg:text-[4.1rem]">
                YOUR WEEK.
                <br />
                YOUR RANK.
              </h1>

              <p className="mt-6 max-w-lg text-[0.9375rem] leading-relaxed text-muted sm:text-base">
                {APP_SUBTAGLINE}
              </p>

              <div className="mt-8 flex flex-col gap-2.5 sm:flex-row">
                <ButtonLink
                  to={status === 'loading' ? '/login' : signedIn ? '/dashboard' : '/signup'}
                  size="lg"
                  icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
                  className="flex-row-reverse"
                >
                  {signedIn ? 'Go to dashboard' : 'Start competing'}
                </ButtonLink>
                <ButtonLink to="/leaderboard" variant="secondary" size="lg">
                  View leaderboard
                </ButtonLink>
              </div>

              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2">
                {['Free to join', 'Three photos', 'One confirmed score'].map((item) => (
                  <li key={item} className="flex items-center gap-1.5 text-[11px] text-muted">
                    <CheckCircle2 className="h-3 w-3 text-forest/60" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <HeroBoard
              entries={entries}
              competition={leaderboard.data?.competition ?? null}
              loading={leaderboard.loading}
              unavailable={unavailable}
              signedIn={signedIn}
            />
          </div>

          {backendMode === 'unconfigured' ? (
            <BackendBanner className="mt-10 lg:max-w-2xl" />
          ) : null}
        </div>
      </section>

      <section aria-label="Competition structure" className="border-b border-line bg-surface">
        <div className="container-page">
          <dl className="grid divide-y divide-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {FACTS.map((fact) => (
              <div key={fact.label} className="flex items-baseline gap-4 py-6 sm:px-7 sm:first:pl-0 sm:last:pr-0">
                <dt className="sr-only">{fact.label}</dt>
                <dd className="font-serif text-3xl italic leading-none text-gold-deep">
                  {fact.value}
                </dd>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink">
                    {fact.label}
                  </p>
                  <p className="mt-1 text-[11px] text-muted">{fact.detail}</p>
                </div>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <HowItWorks />

      <WeekPanel
        competition={leaderboard.data?.competition ?? null}
        leaderboard={leaderboard.data}
        unavailable={unavailable}
      />

      <TopTenPreview
        entries={entries}
        loading={leaderboard.loading}
        unavailable={unavailable}
        signedIn={signedIn}
      />

      <RulesSummary />

      <section className="border-t border-line bg-surface">
        <div className="container-page py-8">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <p className="text-[11px] uppercase tracking-[0.14em] text-muted">
              A note on the score
            </p>
            <p className="max-w-3xl text-[11px] leading-relaxed text-muted">
              {ENTERTAINMENT_DISCLAIMER}{' '}
              <Link
                to="/rules#scoring"
                className="font-medium text-forest underline underline-offset-2"
              >
                How scoring works
              </Link>
            </p>
          </div>
        </div>
      </section>

      <ClosingCta signedIn={signedIn} />
    </>
  )
}
