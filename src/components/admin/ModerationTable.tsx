import { Link } from 'react-router-dom'
import type { ModerationReport } from '@/types/domain'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/States'
import { formatRelativeTime } from '@/utils/datetime'

const STATUS_VARIANT = {
  pending: 'warning',
  actioned: 'success',
  dismissed: 'neutral',
} as const

export function ModerationTable({
  reports,
  onResolve,
  busyId,
}: {
  reports: ModerationReport[]
  onResolve: (report: ModerationReport, action: 'actioned' | 'dismissed') => void
  busyId: string | null
}) {
  if (reports.length === 0) {
    return (
      <EmptyState
        title="The moderation queue is empty."
        description="New reports from public profiles appear here for human review. Reports never automatically ban an account."
        className="border-0 bg-transparent"
      />
    )
  }

  return (
    <>
      <div className="divide-y divide-line md:hidden">
        {reports.map((report) => (
          <div key={report.id} className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-ink">{report.categoryLabel}</p>
                <p className="mt-1 text-[11px] text-muted">
                  Reported:{' '}
                  <Link
                    to={`/profile/${encodeURIComponent(report.reportedUsername)}`}
                    className="text-forest underline underline-offset-2"
                  >
                    @{report.reportedUsername}
                  </Link>
                </p>
                <p className="mt-0.5 text-[10px] text-muted">
                  By @{report.reporterUsername} · {formatRelativeTime(report.createdAt)}
                </p>
              </div>
              <Badge variant={STATUS_VARIANT[report.status]}>{report.status}</Badge>
            </div>
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                className="flex-1"
                loading={busyId === report.id}
                disabled={report.status !== 'pending'}
                onClick={() => onResolve(report, 'actioned')}
              >
                Action taken
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="flex-1"
                disabled={report.status !== 'pending'}
                onClick={() => onResolve(report, 'dismissed')}
              >
                Dismiss
              </Button>
            </div>
          </div>
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line">
              {['Category', 'Reported', 'Reporter', 'Received', 'Status', 'Decision'].map(
                (heading) => (
                  <th
                    key={heading}
                    scope="col"
                    className="px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted"
                  >
                    {heading}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {reports.map((report) => (
              <tr key={report.id} className="align-middle">
                <td className="px-4 py-3.5">
                  <p className="text-xs font-medium text-ink">{report.categoryLabel}</p>
                </td>
                <td className="px-4 py-3.5">
                  <Link
                    to={`/profile/${encodeURIComponent(report.reportedUsername)}`}
                    className="text-xs text-forest hover:underline"
                  >
                    @{report.reportedUsername}
                  </Link>
                </td>
                <td className="px-4 py-3.5 text-xs text-muted">@{report.reporterUsername}</td>
                <td className="whitespace-nowrap px-4 py-3.5 text-[11px] text-muted">
                  {formatRelativeTime(report.createdAt)}
                </td>
                <td className="px-4 py-3.5">
                  <Badge variant={STATUS_VARIANT[report.status]}>{report.status}</Badge>
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex gap-1.5">
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={busyId === report.id}
                      disabled={report.status !== 'pending'}
                      onClick={() => onResolve(report, 'actioned')}
                      className="!h-7 !px-2 !text-[9px]"
                    >
                      Action taken
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={report.status !== 'pending'}
                      onClick={() => onResolve(report, 'dismissed')}
                      className="!h-7 !px-2 !text-[9px]"
                    >
                      Dismiss
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
