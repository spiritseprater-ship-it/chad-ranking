import { Link } from 'react-router-dom'
import { ArrowRight, CalendarClock } from 'lucide-react'
import type { Competition, LeaderboardEntry } from '@/types/domain'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { EmptyState, Skeleton } from '@/components/ui/States'
import { ButtonLink } from '@/components/ui/Button'
import { SampleDataTag } from '@/components/common/BackendBanner'
import { CompetitionCountdown } from '@/components/common/CompetitionCountdown'
import { formatIstDateTime } from '@/utils/datetime'

/**
 * Landing-page Top 3 board. It never invents winners: an empty database shows
 * an empty state, and a misconfigured backend shows a neutral notice.
 */
export function HeroBoard({
  entries,
  competition,
  loading,
  unavailable,
  signedIn,
}: {
  entries: LeaderboardEntry[]
  competition: Competition | null
  loading: boolean
  unavailable: boolean
  signedIn: boolean
}) {
  return (
    <div className="relative overflow-hidden rounded-card border border-line bg-surface shadow-soft">
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4 sm:px-6">
        <div>
          <p className="eyebrow">This week’s board</p>
          <p className="mt-1.5 font-display text-sm font-semibold text-ink">
            {competition ? competition.weekLabel : 'Weekly competition'}
          </p>
        </div>
        <SampleDataTag />
      </div>

      <div className="px-5 py-5 sm:px-6">
        {loading ? (
          <div className="space-y-4" role="status" aria-label="Loading top three">
            {[0, 1, 2].map((index) => (
              <div key={index} className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className="h-2.5 w-16" />
                </div>
                <Skeleton className="h-4 w-8" />
              </div>
            ))}
          </div>
        ) : unavailable ? (
          <div className="py-6 text-center">
            <p className="font-display text-sm font-semibold text-ink">
              The live board is not connected.
            </p>
            <p className="mx-auto mt-2 max-w-xs text-xs leading-relaxed text-muted">
              This build has no Firebase project configured, so no production
              ranking is shown here.
            </p>
            <Link
              to="/rules#data-status"
              className="mt-4 inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-forest underline-offset-4 hover:underline"
            >
              Read data status
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={CalendarClock}
            title="The leaderboard is waiting for its first challenger."
            description="Be the first confirmed score of the week."
            action={
              <ButtonLink to={signedIn ? '/submit' : '/signup'} size="sm">
                {signedIn ? 'Enter this week' : 'Join the competition'}
              </ButtonLink>
            }
            className="border-0 bg-transparent px-0 py-6"
          />
        ) : (
          <ol className="divide-y divide-line">
            {entries.slice(0, 3).map((entry) => (
              <li key={entry.uid}>
                <Link
                  to={`/profile/${encodeURIComponent(entry.username)}`}
                  className="group flex items-center gap-3.5 py-3.5 transition-colors hover:bg-subtle/40"
                >
                  <span className="w-5 shrink-0 font-serif text-sm italic text-muted">
                    {String(entry.rank).padStart(2, '0')}
                  </span>
                  <ProfileAvatar
                    username={entry.username}
                    imagePath={entry.profileImagePath}
                    size="sm"
                    ring={entry.rank === 1 ? 'gold' : 'none'}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{entry.username}</p>
                    <p className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-muted">
                      {entry.title}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="font-display text-base font-semibold tabular-nums text-ink">
                      {entry.score}
                    </span>
                    <span className="ml-0.5 text-[10px] text-muted">/100</span>
                  </div>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </div>

      {competition && !unavailable ? (
        <div className="border-t border-line bg-subtle/40 px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CompetitionCountdown endsAt={competition.endsAt} label="Closes in" eyebrow="Reset" />
            <Link
              to="/leaderboard"
              className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-forest hover:underline underline-offset-4"
            >
              Full board
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>
          <p className="mt-3 text-[10px] text-muted">
            Reset {formatIstDateTime(competition.endsAt)} · Asia/Kolkata
          </p>
        </div>
      ) : null}
    </div>
  )
}
