import { ScrollText } from 'lucide-react'
import { services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States'
import { Notice } from '@/components/ui/Notice'
import { formatIstDateTime, formatRelativeTime } from '@/utils/datetime'

export function AdminAuditPage() {
  useDocumentTitle('Admin · Audit log')
  const audit = useAsync(() => services.admin.getAuditEvents(), [])
  const events = audit.data ?? []

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Audit log</p>
        <h2 className="mt-1.5 font-display text-xl font-semibold text-ink">
          Administrative record
        </h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted">
          A minimal record of administrative events: what happened, who did it, to which
          account, the reason and when. Raw photos, emails and leaderboard snapshots are
          never stored here.
        </p>
      </div>

      {audit.loading ? (
        <LoadingState label="Loading audit log…" />
      ) : audit.error ? (
        <ErrorState
          title="Audit log unavailable"
          message={audit.error.userMessage}
          code={audit.error.code}
          onRetry={audit.reload}
        />
      ) : events.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No administrative actions yet."
          description="Score corrections, suspensions, removals and reset results will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-card border border-line bg-surface">
          <ul className="divide-y divide-line">
            {events.map((event) => (
              <li key={event.id} className="px-4 py-4 sm:px-5">
                <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-ink">{event.actionLabel}</p>
                      {event.targetUsername ? (
                        <Badge variant="neutral">@{event.targetUsername}</Badge>
                      ) : (
                        <Badge variant="outline">Competition-wide</Badge>
                      )}
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted">
                      {event.reason}
                    </p>
                    <p className="mt-2 text-[10px] text-muted">
                      by {event.actorUsername} · {formatIstDateTime(event.createdAt)}
                    </p>
                  </div>
                  <p className="shrink-0 text-[10px] text-muted">
                    {formatRelativeTime(event.createdAt)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Notice variant="neutral" title="Retention">
        Audit records are kept only as long as needed for moderation accountability — a
        short, documented retention period — and never contain previous leaderboard
        snapshots or participant photographs.
      </Notice>
    </div>
  )
}
