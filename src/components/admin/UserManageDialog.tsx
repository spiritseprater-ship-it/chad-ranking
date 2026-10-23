import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import type { AdminUserSummary } from '@/types/domain'
import { services } from '@/services'
import { getErrorMessage } from '@/services/errors'
import { useToast } from '@/hooks/useToast'
import { Modal, ConfirmDialog } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Field, Select, TextArea, TextInput } from '@/components/ui/Form'
import { Notice } from '@/components/ui/Notice'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { formatIstDate } from '@/utils/datetime'

type ManageAction =
  | 'suspend'
  | 'restore'
  | 'correct-score'
  | 'remove-showcase'
  | 'disqualify'
  | 'restore-submission'
  | 'remove-profile-picture'

const ACTION_LABELS: Record<ManageAction, string> = {
  suspend: 'Suspend account',
  restore: 'Restore account',
  'correct-score': 'Correct confirmed score',
  'remove-showcase': 'Remove showcase',
  disqualify: 'Disqualify submission',
  'restore-submission': 'Restore submission',
  'remove-profile-picture': 'Remove profile picture',
}

const DANGEROUS: ManageAction[] = [
  'suspend',
  'remove-showcase',
  'disqualify',
  'remove-profile-picture',
]

export function UserManageDialog({
  open,
  summary,
  onClose,
  onChanged,
}: {
  open: boolean
  summary: AdminUserSummary | null
  onClose: () => void
  onChanged: () => void
}) {
  const { toast } = useToast()
  const [action, setAction] = useState<ManageAction>('suspend')
  const [score, setScore] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open || !summary) return
    setAction(summary.accountStatus === 'active' ? 'suspend' : 'restore')
    setScore(summary.confirmedScore !== null ? String(summary.confirmedScore) : '')
    setReason('')
    setError(null)
    setConfirmOpen(false)
    setSubmitting(false)
  }, [open, summary])

  if (!summary) return null

  const validate = (): boolean => {
    if (reason.trim().length < 3) {
      setError('Record a short reason (at least 3 characters). It is stored in the audit log.')
      return false
    }
    if (action === 'correct-score') {
      const numeric = Number(score)
      if (!Number.isInteger(numeric) || numeric < 0 || numeric > 100) {
        setError('Scores must be whole numbers from 0 to 100.')
        return false
      }
    }
    setError(null)
    return true
  }

  const apply = async () => {
    setSubmitting(true)
    setError(null)
    try {
      switch (action) {
        case 'suspend':
          await services.admin.suspendUser({ uid: summary.uid, reason })
          break
        case 'restore':
          await services.admin.restoreUser({ uid: summary.uid, reason })
          break
        case 'correct-score':
          await services.admin.correctScore({
            uid: summary.uid,
            score: Number(score),
            reason,
          })
          break
        case 'remove-showcase':
          await services.admin.removeShowcase({ uid: summary.uid, reason })
          break
        case 'disqualify':
          await services.admin.disqualifySubmission({ uid: summary.uid, reason })
          break
        case 'restore-submission':
          await services.admin.restoreSubmission({ uid: summary.uid, reason })
          break
        case 'remove-profile-picture':
          await services.admin.removeProfilePicture({ uid: summary.uid, reason })
          break
      }
      toast({
        variant: 'success',
        title: ACTION_LABELS[action],
        description: `Recorded for @${summary.username}. Rankings recalculate from confirmed data.`,
      })
      setConfirmOpen(false)
      onChanged()
      onClose()
    } catch (cause) {
      setError(getErrorMessage(cause))
      setConfirmOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  const requiresConfirmation = DANGEROUS.includes(action) || action === 'restore-submission'

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={`Manage @${summary.username}`}
        description="Administrative actions are written to a minimal audit trail. Scores remain derived from confirmed values — ranks are never edited directly."
        size="md"
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            <Link
              to={`/profile/${encodeURIComponent(summary.username)}`}
              className="inline-flex h-9 items-center justify-center text-[10px] font-semibold uppercase tracking-[0.1em] text-forest underline underline-offset-4"
            >
              View public profile
            </Link>
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <Button variant="secondary" onClick={onClose} disabled={submitting}>
                Cancel
              </Button>
              <Button
                variant={DANGEROUS.includes(action) ? 'danger' : 'primary'}
                onClick={() => {
                  if (validate()) setConfirmOpen(true)
                }}
                disabled={submitting}
              >
                Review action
              </Button>
            </div>
          </div>
        }
      >
        <div className="mb-5 flex items-center gap-3 rounded-lg border border-line bg-canvas/60 px-3 py-3">
          <ProfileAvatar username={summary.username} size="sm" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-ink">{summary.username}</p>
            <p className="mt-0.5 text-[10px] text-muted">
              Joined {formatIstDate(summary.createdAt)} · Role {summary.role}
            </p>
          </div>
          <div className="flex shrink-0 gap-1.5">
            <Badge variant={summary.accountStatus === 'active' ? 'success' : 'danger'}>
              {summary.accountStatus}
            </Badge>
            {summary.moderationStatus === 'disqualified' ? (
              <Badge variant="danger">DQ</Badge>
            ) : null}
          </div>
        </div>

        <div className="space-y-4">
          <Field id="admin-action" label="Action" required>
            <Select
              id="admin-action"
              value={action}
              onChange={(event) => {
                setAction(event.target.value as ManageAction)
                setError(null)
              }}
            >
              <option value="suspend" disabled={summary.accountStatus === 'suspended'}>
                Suspend account
              </option>
              <option value="restore" disabled={summary.accountStatus === 'active'}>
                Restore account
              </option>
              <option value="correct-score" disabled={summary.confirmedScore === null}>
                Correct confirmed score
              </option>
              <option value="remove-showcase" disabled={!summary.hasShowcase}>
                Remove showcase
              </option>
              <option value="disqualify" disabled={summary.confirmedScore === null}>
                Disqualify submission
              </option>
              <option
                value="restore-submission"
                disabled={summary.moderationStatus !== 'disqualified'}
              >
                Restore disqualified submission
              </option>
              <option value="remove-profile-picture">Remove profile picture</option>
            </Select>
          </Field>

          {action === 'correct-score' ? (
            <Field
              id="admin-score"
              label="New confirmed score"
              required
              hint="Whole number from 0 to 100. Top 10 eligibility and ranks are recalculated automatically."
            >
              <TextInput
                id="admin-score"
                type="number"
                min={0}
                max={100}
                step={1}
                value={score}
                onChange={(event) => setScore(event.target.value)}
                className="h-11"
              />
            </Field>
          ) : null}

          <Field
            id="admin-reason"
            label="Reason for the action"
            required
            hint="Stored in the minimal audit record. Do not include private information about the participant."
          >
            <TextArea
              id="admin-reason"
              rows={3}
              value={reason}
              onChange={(event) => setReason(event.target.value.slice(0, 240))}
              placeholder="e.g. Reported impersonation; verified with the affected participant."
            />
          </Field>

          {DANGEROUS.includes(action) ? (
            <Notice variant="warning" title="Destructive action">
              <span className="flex items-start gap-2">
                <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                This immediately changes public visibility. Suspending an account hides
                its rank; removing a showcase also removes its stored image.
              </span>
            </Notice>
          ) : null}

          {error ? <Notice variant="danger" title="Action not applied">{error}</Notice> : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={apply}
        title={`Confirm: ${ACTION_LABELS[action]}?`}
        description={
          <>
            Target <strong className="text-ink">@{summary.username}</strong>.{' '}
            <span className="block mt-2">Reason: “{reason.trim()}”</span>
            {action === 'correct-score' ? (
              <span className="mt-2 block">
                New score: <strong className="text-ink">{score}/100</strong>
              </span>
            ) : null}
            <span className="mt-3 block text-[11px]">
              This is recorded in the audit log. It cannot be undone automatically.
            </span>
          </>
        }
        confirmLabel={requiresConfirmation ? 'Apply action' : 'Apply'}
        variant={DANGEROUS.includes(action) ? 'danger' : 'primary'}
        loading={submitting}
      />
    </>
  )
}
