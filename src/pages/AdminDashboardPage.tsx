import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BarChart3,
  Gavel,
  ListOrdered,
  RefreshCw,
  ShieldAlert,
  Trophy,
  UserCheck,
  UserX,
  Users,
} from 'lucide-react'
import { services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useToast } from '@/hooks/useToast'
import { getErrorMessage } from '@/services/errors'
import { AdminStatCard } from '@/components/admin/AdminStatCard'
import { LeaderboardRow } from '@/components/common/LeaderboardRow'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/Modal'
import { ErrorState, Skeleton } from '@/components/ui/States'
import { Notice } from '@/components/ui/Notice'
import { Badge } from '@/components/ui/Badge'
import { formatRelativeTime } from '@/utils/datetime'

export function AdminDashboardPage() {
  useDocumentTitle('Admin overview')
  const { toast } = useToast()
  const overview = useAsync(() => services.admin.getOverview(), [])
  const [recalcOpen, setRecalcOpen] = useState(false)
  const [recalculating, setRecalculating] = useState(false)
  const [recalcError, setRecalcError] = useState<string | null>(null)

  const handleRecalculate = async () => {
    setRecalculating(true)
    setRecalcError(null)
    try {
      const result = await services.admin.recalculateRankings()
      toast({
        variant: 'success',
        title: 'Rankings recalculated',
        description: `${result.rankedCount} ranked positions derived from confirmed scores.`,
      })
      setRecalcOpen(false)
      overview.reload()
    } catch (cause) {
      setRecalcError(getErrorMessage(cause))
      setRecalcOpen(false)
    } finally {
      setRecalculating(false)
    }
  }

  const data = overview.data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Overview</p>
          <h2 className="mt-1.5 font-display text-xl font-semibold text-ink">
            {data ? `Week ${data.competition.weekLabel}` : 'This week'}
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setRecalcOpen(true)}
            icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}
            disabled={!data}
          >
            Recalculate rankings
          </Button>
          <Link
            to="/admin/users"
            className="inline-flex h-9 items-center gap-1.5 rounded-field bg-forest px-3.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-white transition hover:bg-forest-700"
          >
            Manage users
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {recalcError ? (
        <Notice variant="danger" title="Recalculation failed">
          {recalcError}
        </Notice>
      ) : null}

      {overview.loading ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-28 rounded-card" />
            ))}
          </div>
          <Skeleton className="h-72 rounded-card" />
        </div>
      ) : overview.error ? (
        <ErrorState
          title="Admin overview unavailable"
          message={overview.error.userMessage}
          code={overview.error.code}
          onRetry={overview.reload}
        />
      ) : data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <AdminStatCard
              label="Total registered accounts"
              value={data.stats.totalUsers}
              hint="Includes suspended and unranked accounts."
              icon={Users}
            />
            <AdminStatCard
              label="Confirmed participants"
              value={data.stats.activeParticipants}
              hint="Confirmed, non-disqualified entries this week."
              icon={UserCheck}
              tone="forest"
            />
            <AdminStatCard
              label="Official Top 100"
              value={data.stats.rankedCount}
              hint={`${data.stats.belowCutoffCount} confirmed below the cutoff.`}
              icon={ListOrdered}
            />
            <AdminStatCard
              label="Top 10"
              value={data.stats.topTenCount}
              hint="Showcase-eligible positions."
              icon={Trophy}
              tone="gold"
            />
            <AdminStatCard
              label="Pending moderation"
              value={data.stats.pendingReports}
              hint="Reports awaiting a human decision."
              icon={Gavel}
              tone={data.stats.pendingReports > 0 ? 'danger' : 'neutral'}
            />
            <AdminStatCard
              label="Suspended accounts"
              value={data.stats.suspendedCount}
              hint="Excluded from the active ranking."
              icon={UserX}
              tone={data.stats.suspendedCount > 0 ? 'danger' : 'neutral'}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <section className="overflow-hidden rounded-card border border-line bg-surface">
              <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-gold-deep" aria-hidden="true" />
                  <h3 className="font-display text-sm font-semibold text-ink">
                    Current Top 10
                  </h3>
                </div>
                <Badge variant="gold">Showcase eligible</Badge>
              </div>
              {data.topTen.length === 0 ? (
                <p className="px-5 py-8 text-center text-xs text-muted">
                  No confirmed participants this week.
                </p>
              ) : (
                <div className="grid sm:grid-cols-2">
                  {data.topTen.map((entry) => (
                    <LeaderboardRow key={entry.uid} entry={entry} showAvatar />
                  ))}
                </div>
              )}
              <div className="border-t border-line px-5 py-3">
                <Link
                  to="/leaderboard"
                  className="inline-flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-forest hover:underline underline-offset-4"
                >
                  Full public leaderboard
                  <ArrowRight className="h-3 w-3" aria-hidden="true" />
                </Link>
              </div>
            </section>

            <section className="rounded-card border border-line bg-surface">
              <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
                <div className="flex items-center gap-2">
                  <Gavel className="h-4 w-4 text-forest" aria-hidden="true" />
                  <h3 className="font-display text-sm font-semibold text-ink">
                    Pending reports
                  </h3>
                </div>
                <Badge variant={data.stats.pendingReports > 0 ? 'warning' : 'neutral'}>
                  {data.stats.pendingReports} open
                </Badge>
              </div>
              {data.pendingReports.length === 0 ? (
                <p className="px-5 py-8 text-center text-xs text-muted">
                  Nothing waiting for review.
                </p>
              ) : (
                <ul className="divide-y divide-line">
                  {data.pendingReports.slice(0, 5).map((report) => (
                    <li key={report.id} className="px-5 py-3.5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-medium text-ink">
                            {report.categoryLabel}
                          </p>
                          <p className="mt-0.5 text-[10px] text-muted">
                            @{report.reportedUsername} · {formatRelativeTime(report.createdAt)}
                          </p>
                        </div>
                        <Link
                          to="/admin/moderation"
                          className="shrink-0 text-[9px] font-semibold uppercase tracking-[0.1em] text-forest underline underline-offset-2"
                        >
                          Review
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <div className="border-t border-line px-5 py-3">
                <Link
                  to="/admin/moderation"
                  className="inline-flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-forest hover:underline underline-offset-4"
                >
                  Moderation queue
                  <ArrowRight className="h-3 w-3" aria-hidden="true" />
                </Link>
              </div>
            </section>
          </div>

          <section className="rounded-card border border-line bg-surface">
            <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-forest" aria-hidden="true" />
                <h3 className="font-display text-sm font-semibold text-ink">
                  Recent administrative actions
                </h3>
              </div>
              <Link
                to="/admin/audit"
                className="text-[9px] font-semibold uppercase tracking-[0.12em] text-forest underline underline-offset-4"
              >
                Full audit log
              </Link>
            </div>
            {data.recentAudit.length === 0 ? (
              <p className="px-5 py-8 text-center text-xs text-muted">
                No administrative actions recorded this week.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {data.recentAudit.map((event) => (
                  <li key={event.id} className="flex flex-col gap-1 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-xs font-medium text-ink">
                        {event.actionLabel}
                        {event.targetUsername ? (
                          <span className="text-muted"> · @{event.targetUsername}</span>
                        ) : null}
                      </p>
                      <p className="mt-0.5 text-[10px] leading-relaxed text-muted">
                        {event.reason}
                      </p>
                    </div>
                    <p className="shrink-0 text-[10px] text-muted">
                      {event.actorUsername} · {formatRelativeTime(event.createdAt)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <Notice variant="neutral" title="Operational notes">
            <ul className="mt-1 space-y-1.5 text-[11px]">
              <li className="flex gap-2">
                <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                Suspended accounts are excluded from the public ranking immediately.
              </li>
              <li>Score corrections are audited and trigger a rank recalculation.</li>
              <li>
                Showcase removal is real deletion: the record and image reference are
                removed, not merely hidden.
              </li>
            </ul>
          </Notice>
        </>
      ) : null}

      <ConfirmDialog
        open={recalcOpen}
        onClose={() => setRecalcOpen(false)}
        onConfirm={handleRecalculate}
        title="Recalculate all rankings?"
        description="Ranks are always derived from confirmed scores and the documented tie-breakers. This action re-derives them and writes an audit entry; it cannot change a score by itself."
        confirmLabel="Recalculate"
        loading={recalculating}
      />
    </div>
  )
}
