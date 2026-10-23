import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Users } from 'lucide-react'
import { services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { PageHeader } from '@/components/ui/PageHeader'
import { TextInput } from '@/components/ui/Form'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { Pagination } from '@/components/common/Pagination'
import { SampleDataTag } from '@/components/common/BackendBanner'
import { cn } from '@/utils/cn'

const PAGE_SIZE = 24

export function ParticipantsPage() {
  useDocumentTitle('Participant directory')
  const leaderboard = useAsync(() => services.leaderboard.getLeaderboard(), [])
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)

  const directory = leaderboard.data?.directory ?? []
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return directory
    return directory.filter((entry) => entry.username.toLowerCase().includes(needle))
  }, [directory, query])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const rows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  useEffect(() => {
    setPage(1)
  }, [query, leaderboard.data?.competition.id])

  return (
    <>
      <PageHeader
        eyebrow="Separate from the official leaderboard"
        title="Participant directory"
        description="Participants ranked below 100, listed by username only. Scores, pictures and showcases are never shown here, and this directory is not an extension of the Top 100."
        actions={<SampleDataTag />}
      />

      <div className="container-page py-8 lg:py-10">
        {leaderboard.loading ? (
          <LoadingState label="Loading participants…" />
        ) : leaderboard.error ? (
          <ErrorState
            title="Directory unavailable"
            message={leaderboard.error.userMessage}
            code={leaderboard.error.code}
            onRetry={leaderboard.reload}
          />
        ) : (
          <>
            <div className="rounded-card border border-line bg-surface">
              <div className="flex flex-col justify-between gap-4 border-b border-line p-4 sm:flex-row sm:items-center sm:px-5">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-forest" aria-hidden="true" />
                  <p className="text-sm font-medium text-ink">
                    {directory.length} participant{directory.length === 1 ? '' : 's'} below rank 100
                  </p>
                </div>
                <div className="relative w-full sm:max-w-xs">
                  <Search
                    className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
                    aria-hidden="true"
                  />
                  <TextInput
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search by username"
                    className="h-10 pl-9 text-xs"
                    aria-label="Search participants by username"
                  />
                </div>
              </div>

              {directory.length === 0 ? (
                <EmptyState
                  icon={Users}
                  title="No one is below the Top 100."
                  description="Either every confirmed participant is inside the official leaderboard, or no scores have been confirmed this week."
                  action={
                    <Link
                      to="/leaderboard"
                      className="text-xs font-semibold uppercase tracking-[0.1em] text-forest underline underline-offset-4"
                    >
                      View the leaderboard
                    </Link>
                  }
                  className="border-0 bg-transparent"
                />
              ) : filtered.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title="No participant matches that username."
                  description="Usernames are matched case-insensitively. Only participants below rank 100 are listed here."
                  action={
                    <button
                      type="button"
                      onClick={() => setQuery('')}
                      className="text-xs font-semibold uppercase tracking-[0.1em] text-forest underline underline-offset-4"
                    >
                      Clear search
                    </button>
                  }
                  className="border-0 bg-transparent"
                />
              ) : (
                <>
                  <ul className="divide-y divide-line">
                    {rows.map((entry) => (
                      <li key={entry.uid}>
                        <Link
                          to={`/profile/${encodeURIComponent(entry.username)}`}
                          className={cn(
                            'group flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-subtle/60 sm:px-5',
                          )}
                        >
                          <span className="w-10 shrink-0 font-display text-xs font-semibold tabular-nums text-muted">
                            {entry.rank}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
                            {entry.username}
                          </span>
                          <span className="text-[10px] uppercase tracking-[0.1em] text-muted transition-colors group-hover:text-forest">
                            Profile
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center justify-between px-4 pt-3 sm:px-5">
                    <p className="text-[10px] text-muted">
                      Showing {(currentPage - 1) * PAGE_SIZE + 1}–
                      {Math.min(currentPage * PAGE_SIZE, filtered.length)} of {filtered.length}
                    </p>
                    {leaderboard.data && leaderboard.data.unconfirmedCount > 0 ? (
                      <p className="hidden text-[10px] text-muted sm:block">
                        {leaderboard.data.unconfirmedCount} active account
                        {leaderboard.data.unconfirmedCount === 1 ? '' : 's'} not yet confirmed
                      </p>
                    ) : null}
                  </div>
                  <Pagination
                    page={currentPage}
                    pageCount={pageCount}
                    onPageChange={setPage}
                    label="Participant directory pages"
                  />
                </>
              )}
            </div>

            <div className="mt-6 rounded-lg border border-line bg-subtle/40 px-4 py-3">
              <p className="text-[11px] leading-relaxed text-muted">
                Search runs against the usernames returned for this competition
                period. In Phase 2 the directory is paginated in Firestore and the
                search field queries only public username data — never emails or
                private account details.
              </p>
            </div>
          </>
        )}
      </div>
    </>
  )
}
