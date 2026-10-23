import { Link } from 'react-router-dom'
import { ArrowRight, Trophy } from 'lucide-react'
import type { LeaderboardEntry } from '@/types/domain'
import { SectionHeading } from '@/components/ui/PageHeader'
import { TopRankCard } from '@/components/common/TopRankCard'
import { LeaderboardRow } from '@/components/common/LeaderboardRow'
import { EmptyState, Skeleton } from '@/components/ui/States'
import { ButtonLink } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'

export function TopTenPreview({
  entries,
  loading,
  unavailable,
  signedIn,
}: {
  entries: LeaderboardEntry[]
  loading: boolean
  unavailable: boolean
  signedIn: boolean
}) {
  const topThree = entries.slice(0, 3)
  const rest = entries.slice(3, 10)

  return (
    <section className="border-t border-line bg-surface">
      <div className="container-page py-16 sm:py-20">
        <SectionHeading
          index="II."
          eyebrow="The showcase"
          title="The Top 10 set the standard."
          description="Ten places. One exclusive showcase. Every photograph is user-submitted and visible only while that participant is eligible."
          action={
            <ButtonLink to="/leaderboard" variant="secondary" size="sm">
              Full leaderboard
            </ButtonLink>
          }
        />

        {loading ? (
          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-52 rounded-card" />
            ))}
          </div>
        ) : unavailable ? (
          <Notice variant="warning" title="Top 10 preview unavailable" className="mt-10">
            This build is not connected to a backend, so no participant data is
            displayed here. Nothing is simulated as a real winner.
          </Notice>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={Trophy}
            title="No one has claimed a place yet."
            description="The first confirmed score of the week starts the board."
            action={
              <ButtonLink to={signedIn ? '/submit' : '/signup'} size="sm">
                {signedIn ? 'Start your submission' : 'Join the competition'}
              </ButtonLink>
            }
            className="mt-10"
          />
        ) : (
          <>
            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {topThree.map((entry) => (
                <TopRankCard key={entry.uid} entry={entry} />
              ))}
            </div>

            {rest.length > 0 ? (
              <div className="mt-4 rounded-card border border-line bg-canvas/50">
                <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3.5 sm:px-5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                    Places 4 – 10
                  </p>
                  <Link
                    to="/leaderboard"
                    className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-forest hover:underline underline-offset-4"
                  >
                    View all
                    <ArrowRight className="h-3 w-3" aria-hidden="true" />
                  </Link>
                </div>
                <div className="grid sm:grid-cols-2">
                  {rest.map((entry) => (
                    <LeaderboardRow
                      key={entry.uid}
                      entry={entry}
                      showAvatar
                      isCurrentUser={false}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            <p className="mt-5 text-[11px] leading-relaxed text-muted">
              Profile pictures appear only for the current Top 10. Ranks 11–100
              show username and score; participants below 100 appear in the
              directory by username only.
            </p>
          </>
        )}
      </div>
    </section>
  )
}
