import { CalendarClock, Users } from 'lucide-react'
import type { Competition, LeaderboardView } from '@/types/domain'
import { CompetitionCountdown } from '@/components/common/CompetitionCountdown'
import { ButtonLink } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'
import { SampleDataTag } from '@/components/common/BackendBanner'
import { formatIstDateTime } from '@/utils/datetime'

const RULES = [
  'One confirmed score per participant, per week.',
  'Ranking: score descending, then earliest submission, then account ID.',
  'Top 100 are ranked; everyone else appears in the participant directory.',
  'The week closes Monday at 00:00 IST.',
]

export function WeekPanel({
  competition,
  leaderboard,
  unavailable,
}: {
  competition: Competition | null
  leaderboard: LeaderboardView | null
  unavailable: boolean
}) {
  return (
    <section className="border-t border-line bg-canvas">
      <div className="container-page py-16 sm:py-20">
        <div className="overflow-hidden rounded-card bg-forest-900 text-canvas paper-texture">
          <div className="grid gap-10 p-6 sm:p-9 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:p-12">
            <div>
              <div className="flex items-center gap-3">
                <span className="gold-rule" aria-hidden="true" />
                <p className="text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-canvas/65">
                  The weekly competition
                </p>
                <SampleDataTag />
              </div>
              <h2 className="mt-5 max-w-md font-display text-3xl font-semibold leading-[1.12] tracking-[-0.02em] text-canvas sm:text-[2.5rem]">
                Every Monday, the slate is clean.
              </h2>
              <p className="mt-4 max-w-md text-sm leading-relaxed text-canvas/70">
                Scores, ranks and showcase content reset automatically. Accounts,
                usernames and profile pictures stay. The reset is handled by a
                trusted scheduled backend — never by a browser timer.
              </p>

              {competition ? (
                <div className="mt-8">
                  <CompetitionCountdown
                    endsAt={competition.endsAt}
                    tone="dark"
                    eyebrow={`Week ${competition.id.replace('w', '')}`}
                    label="Competition ends in"
                  />
                  <p className="mt-5 flex items-center gap-2 text-[11px] text-canvas/70">
                    <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
                    Ends {formatIstDateTime(competition.endsAt)} · Asia/Kolkata
                  </p>
                </div>
              ) : (
                <div className="mt-8">
                  <Notice variant="neutral" className="border-canvas/10 bg-canvas/[0.04]">
                    <span className="text-canvas/70">
                      Competition timing appears here once the backend is
                      configured. No countdown is fabricated.
                    </span>
                  </Notice>
                </div>
              )}

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <ButtonLink to="/leaderboard" variant="inverse" size="sm">
                  View leaderboard
                </ButtonLink>
                <ButtonLink
                  to="/rules"
                  variant="ghost"
                  size="sm"
                  className="text-canvas/70 hover:bg-white/5 hover:text-canvas"
                >
                  Rules & privacy
                </ButtonLink>
              </div>
            </div>

            <div className="flex flex-col justify-between gap-8 border-t border-canvas/10 pt-8 lg:border-l lg:border-t-0 lg:pl-12 lg:pt-0">
              <div>
                <p className="text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-canvas/70">
                  This week in numbers
                </p>
                {unavailable ? (
                  <p className="mt-4 text-sm leading-relaxed text-canvas/55">
                    Participant counts are loaded from the authoritative leaderboard.
                    They are not available in this build.
                  </p>
                ) : leaderboard ? (
                  <dl className="mt-5 grid grid-cols-3 gap-5">
                    <div>
                      <dt className="text-[9px] uppercase tracking-[0.14em] text-canvas/70">
                        Confirmed
                      </dt>
                      <dd className="mt-1.5 font-display text-2xl font-semibold tabular-nums text-canvas">
                        {leaderboard.totalParticipants}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[9px] uppercase tracking-[0.14em] text-canvas/70">
                        Ranked
                      </dt>
                      <dd className="mt-1.5 font-display text-2xl font-semibold tabular-nums text-canvas">
                        {leaderboard.ranked.length}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[9px] uppercase tracking-[0.14em] text-canvas/70">
                        Below 100
                      </dt>
                      <dd className="mt-1.5 font-display text-2xl font-semibold tabular-nums text-canvas">
                        {leaderboard.directory.length}
                      </dd>
                    </div>
                  </dl>
                ) : (
                  <div className="mt-5 h-14 animate-pulse rounded bg-canvas/5" aria-hidden="true" />
                )}
                <p className="mt-4 flex items-center gap-2 text-[10px] text-canvas/55">
                  <Users className="h-3 w-3" aria-hidden="true" />
                  Counts are read live; demo sample counts are labelled.
                </p>
              </div>

              <div>
                <p className="text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-canvas/70">
                  House rules
                </p>
                <ul className="mt-4 space-y-2.5">
                  {RULES.map((rule) => (
                    <li key={rule} className="flex gap-3 text-xs leading-relaxed text-canvas/70">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gold/70" aria-hidden="true" />
                      {rule}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
