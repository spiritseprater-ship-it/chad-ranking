import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, Search, Trophy, Users } from 'lucide-react'
import type { LeaderboardView } from '@/types/domain'
import { backendMode, services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { PageHeader, SectionHeading } from '@/components/ui/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'
import { EmptyState, ErrorState, TableSkeleton } from '@/components/ui/States'
import { TopRankCard } from '@/components/common/TopRankCard'
import { LeaderboardRow } from '@/components/common/LeaderboardRow'
import { CompetitionCountdown } from '@/components/common/CompetitionCountdown'
import { Pagination } from '@/components/common/Pagination'
import { BackendBanner, SampleDataTag } from '@/components/common/BackendBanner'
import { formatIstDateTime } from '@/utils/datetime'

const MIDDLE_PAGE_SIZE = 15

export function LeaderboardPage() {
  useDocumentTitle('Weekly leaderboard')
  const { user } = useAuth()
  const leaderboard = useAsync(() => services.leaderboard.getLeaderboard(), [])
  const [page, setPage] = useState(1)
  const [expired, setExpired] = useState(false)
  const refreshed = useRef(false)
  const competitionId = leaderboard.data?.competition.id

  useEffect(() => {
    setPage(1)
    refreshed.current = false
    setExpired(false)
  }, [competitionId])

  const data: LeaderboardView | null = leaderboard.data
  const topTen = data?.ranked.slice(0, 10) ?? []
  const middle = data?.ranked.slice(10) ?? []
  const pageCount = Math.max(1, Math.ceil(middle.length / MIDDLE_PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageEntries = middle.slice(
    (currentPage - 1) * MIDDLE_PAGE_SIZE,
    currentPage * MIDDLE_PAGE_SIZE,
  )

  const skewMs = useMemo(() => {
    if (!data) return 0
    return new Date(data.generatedAt).getTime() - Date.now()
  }, [data])

  const handleExpire = () => {
    if (refreshed.current) return
    refreshed.current = true
    setExpired(true)
    leaderboard.reload()
  }

  return (
    <>
      <PageHeader
        eyebrow="The competition"
        title="THE WEEKLY LEADERBOARD"
        description="One week. One ranking. A fresh competition every Monday at 00:00 IST. Sorted by confirmed score, then earliest submission, then a stable account ID."
        actions={<SampleDataTag />}
      />

      <div className="container-page py-8 lg:py-10">
        {backendMode !== 'demo' ? <BackendBanner className="mb-6" /> : null}

        {leaderboard.loading && !data ? (
          <div className="space-y-6">
            <div className="rounded-card border border-line bg-surface p-5 sm:p-6">
              <div className="h-3 w-24 animate-pulse rounded bg-subtle" />
              <div className="mt-4 h-10 w-64 animate-pulse rounded bg-subtle" />
            </div>
            <TableSkeleton rows={8} />
          </div>
        ) : leaderboard.error && !data ? (
          <ErrorState
            title="The leaderboard could not be loaded"
            message={leaderboard.error.userMessage}
            code={leaderboard.error.code}
            onRetry={leaderboard.reload}
          />
        ) : data ? (
          <>
            <div className="rounded-card border border-line bg-surface p-5 sm:p-6">
              <div className="grid gap-6 md:grid-cols-[1.2fr_1fr_auto] md:items-center">
                <div>
                  <p className="eyebrow">Current competition</p>
                  <p className="mt-2 font-display text-xl font-semibold tracking-tight text-ink">
                    {data.competition.weekLabel}
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 text-[11px] text-muted">
                    <CalendarDays className="h-3 w-3" aria-hidden="true" />
                    {formatIstDateTime(data.competition.startsAt)} →{' '}
                    {formatIstDateTime(data.competition.endsAt)}
                  </p>
                </div>
                <div>
                  <CompetitionCountdown
                    endsAt={data.competition.endsAt}
                    offsetMs={skewMs}
                    label="Competition ends in"
                    onExpire={handleExpire}
                  />
                </div>
                <div className="flex gap-6 md:justify-end">
                  <div>
                    <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                      Confirmed
                    </p>
                    <p className="mt-1 font-display text-xl font-semibold tabular-nums text-ink">
                      {data.totalParticipants}
                    </p>
                  </div>
                  <div>
                    <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                      Ranked
                    </p>
                    <p className="mt-1 font-display text-xl font-semibold tabular-nums text-ink">
                      {data.ranked.length}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {expired ? (
              <Notice variant="info" title="This week has closed" className="mt-4">
                The next competition is activated by the backend at Monday 00:00 IST.
                This page will show the new period once the backend confirms it.{' '}
                <button
                  type="button"
                  onClick={leaderboard.reload}
                  className="font-medium text-forest underline underline-offset-2"
                >
                  Refresh now
                </button>
              </Notice>
            ) : null}

            {data.ranked.length === 0 ? (
              <EmptyState
                icon={Trophy}
                title="The leaderboard is waiting for its first challenger."
                description="No scores are confirmed for this week yet. The board starts with the first confirmed entry."
                action={
                  user ? (
                    <ButtonLink to="/submit">Join the competition</ButtonLink>
                  ) : (
                    <ButtonLink to="/signup">Join the competition</ButtonLink>
                  )
                }
                className="mt-6"
              />
            ) : (
              <>
                <section className="mt-8" aria-labelledby="top-ten-heading">
                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <p className="eyebrow">Places 1 – {Math.min(10, data.ranked.length)}</p>
                      <h2
                        id="top-ten-heading"
                        className="mt-1.5 font-display text-xl font-semibold text-ink"
                      >
                        The Top 10
                      </h2>
                    </div>
                    <p className="hidden text-[10px] uppercase tracking-[0.12em] text-muted sm:block">
                      Pictures shown for the Top 10 only
                    </p>
                  </div>

                  <div className="mt-5 grid gap-4 lg:grid-cols-3">
                    {topTen.slice(0, 3).map((entry) => (
                      <TopRankCard
                        key={entry.uid}
                        entry={entry}
                        size={entry.rank === 1 ? 'feature' : 'standard'}
                      />
                    ))}
                  </div>

                  {topTen.length > 3 ? (
                    <div className="mt-4 overflow-hidden rounded-card border border-line bg-surface">
                      <div className="grid md:grid-cols-2">
                        {topTen.slice(3).map((entry) => (
                          <LeaderboardRow
                            key={entry.uid}
                            entry={entry}
                            showAvatar
                            isCurrentUser={entry.uid === user?.uid}
                          />
                        ))}
                      </div>
                    </div>
                  ) : null}
                </section>

                <section className="mt-10" aria-label="Official Top 100">
                  <SectionHeading
                    eyebrow={`Places 11 – ${Math.min(100, data.ranked.length)}`}
                    title="The official Top 100"
                    description="Profile pictures are not shown outside the Top 10."
                    action={
                      <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] text-muted">
                        <Users className="h-3 w-3" aria-hidden="true" />
                        {data.ranked.length} ranked
                      </span>
                    }
                  />
                  <div className="mt-5 overflow-hidden rounded-card border border-line bg-surface">
                    {middle.length === 0 ? (
                      <p className="px-5 py-10 text-center text-sm text-muted">
                        No participants between rank 11 and 100 yet.
                      </p>
                    ) : (
                      <>
                        <div className="flex items-center justify-between border-b border-line px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.16em] text-muted sm:px-5">
                          <span>Rank · Participant</span>
                          <span>Score</span>
                        </div>
                        {pageEntries.map((entry) => (
                          <LeaderboardRow
                            key={entry.uid}
                            entry={entry}
                            showAvatar={false}
                            isCurrentUser={entry.uid === user?.uid}
                          />
                        ))}
                        <Pagination
                          page={currentPage}
                          pageCount={pageCount}
                          onPageChange={setPage}
                          label="Official Top 100 pages"
                        />
                      </>
                    )}
                  </div>
                </section>

                <section className="mt-8 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center rounded-card border border-line bg-subtle/40 px-5 py-5">
                  <div>
                    <p className="eyebrow">Below the Top 100</p>
                    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
                      {data.directory.length} confirmed participant
                      {data.directory.length === 1 ? '' : 's'} rank below the official
                      leaderboard. They appear in a separate directory by username only —
                      no score, picture or showcase.
                    </p>
                  </div>
                  <Link
                    to="/participants"
                    className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-forest hover:underline underline-offset-4"
                  >
                    <Search className="h-3 w-3" aria-hidden="true" />
                    Participant directory
                    <ArrowRight className="h-3 w-3" aria-hidden="true" />
                  </Link>
                </section>
              </>
            )}

            <p className="mt-6 text-[10px] leading-relaxed text-muted">
              Ranks are derived from confirmed scores on the backend. The browser
              never submits its own rank. Ties break by earlier confirmation time,
              then by a stable account identifier. Scores are entertainment only.
            </p>
          </>
        ) : null}
      </div>
    </>
  )
}
