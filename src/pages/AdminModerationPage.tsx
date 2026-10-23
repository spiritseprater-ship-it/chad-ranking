import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Info, ShieldCheck } from 'lucide-react'
import type { ModerationReport } from '@/types/domain'
import { services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useToast } from '@/hooks/useToast'
import { getErrorMessage } from '@/services/errors'
import { ModerationTable } from '@/components/admin/ModerationTable'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { Notice } from '@/components/ui/Notice'
import { ConfirmDialog } from '@/components/ui/Modal'
import { cn } from '@/utils/cn'

type Filter = 'pending' | 'all'

export function AdminModerationPage() {
  useDocumentTitle('Admin · Moderation')
  const { toast } = useToast()
  const queue = useAsync(() => services.admin.getModerationQueue(), [])
  const [filter, setFilter] = useState<Filter>('pending')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<{
    report: ModerationReport
    action: 'actioned' | 'dismissed'
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reports = useMemo(() => {
    const all = queue.data ?? []
    return filter === 'pending' ? all.filter((report) => report.status === 'pending') : all
  }, [queue.data, filter])

  const pendingCount = (queue.data ?? []).filter((report) => report.status === 'pending').length

  const handleConfirm = async () => {
    if (!pendingAction) return
    setBusyId(pendingAction.report.id)
    setError(null)
    try {
      await services.admin.resolveReport({
        reportId: pendingAction.report.id,
        action: pendingAction.action,
      })
      toast({
        variant: 'success',
        title:
          pendingAction.action === 'dismissed'
            ? 'Report dismissed'
            : 'Report marked as actioned',
        description:
          pendingAction.action === 'actioned'
            ? 'Now remove the content or suspend the account from Users & scores if required.'
            : 'No action was taken against the account. The decision is recorded.',
      })
      setPendingAction(null)
      queue.reload()
    } catch (cause) {
      setError(getErrorMessage(cause))
      setPendingAction(null)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Moderation</p>
          <h2 className="mt-1.5 font-display text-xl font-semibold text-ink">
            Human review queue
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted">
            Reports are private, rate-limited and never auto-ban an account. Marking a
            report as actioned records the decision — removal or suspension is applied
            separately from Users & scores.
          </p>
        </div>
        <Link
          to="/admin/users"
          className="inline-flex h-9 items-center rounded-field border border-line bg-surface px-3.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:text-ink"
        >
          Open user management
        </Link>
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter reports">
        {(['pending', 'all'] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setFilter(option)}
            aria-pressed={filter === option}
            className={cn(
              'inline-flex h-8 items-center rounded-full border px-3 text-[10px] font-semibold uppercase tracking-[0.1em] transition',
              filter === option
                ? 'border-forest bg-forest text-white'
                : 'border-line bg-surface text-muted hover:text-ink',
            )}
          >
            {option === 'pending' ? `Pending (${pendingCount})` : 'All reports'}
          </button>
        ))}
      </div>

      {error ? (
        <Notice variant="danger" title="Decision not recorded">
          {error}
        </Notice>
      ) : null}

      {queue.loading ? (
        <LoadingState label="Loading moderation queue…" />
      ) : queue.error ? (
        <ErrorState
          title="Moderation queue unavailable"
          message={queue.error.userMessage}
          code={queue.error.code}
          onRetry={queue.reload}
        />
      ) : (
        <div className="overflow-hidden rounded-card border border-line bg-surface">
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
              {reports.length} {filter === 'pending' ? 'pending' : 'total'} report
              {reports.length === 1 ? '' : 's'}
            </p>
            <span className="inline-flex items-center gap-1.5 text-[10px] text-muted">
              <ShieldCheck className="h-3 w-3" aria-hidden="true" />
              Admin-only
            </span>
          </div>
          <ModerationTable
            reports={reports}
            busyId={busyId}
            onResolve={(report, action) => setPendingAction({ report, action })}
          />
        </div>
      )}

      <Notice variant="neutral" title="What gets stored">
        <span className="flex items-start gap-2">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          Reports keep a category, reporter, reported account, status and timestamp only.
          No raw images, accusations or private details are published. The audit record
          contains the action, actor, target, reason and time.
        </span>
      </Notice>

      <ConfirmDialog
        open={pendingAction !== null}
        onClose={() => setPendingAction(null)}
        onConfirm={handleConfirm}
        title={
          pendingAction?.action === 'dismissed'
            ? 'Dismiss this report?'
            : 'Mark this report as actioned?'
        }
        description={
          pendingAction ? (
            <>
              <p>
                Report against{' '}
                <strong className="text-ink">@{pendingAction.report.reportedUsername}</strong>{' '}
                for “{pendingAction.report.categoryLabel}”.
              </p>
              <p className="mt-2 text-[11px]">
                {pendingAction.action === 'dismissed'
                  ? 'The account is not penalised. The dismissal is recorded in the audit log.'
                  : 'This only records the moderation decision. Remove the showcase, picture or submission from the user’s management dialog as needed.'}
              </p>
            </>
          ) : null
        }
        confirmLabel={pendingAction?.action === 'dismissed' ? 'Dismiss report' : 'Mark actioned'}
        variant={pendingAction?.action === 'dismissed' ? 'primary' : 'danger'}
        loading={busyId !== null}
      />
    </div>
  )
}
