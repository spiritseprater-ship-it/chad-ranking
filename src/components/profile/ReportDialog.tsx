import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { REPORT_CATEGORIES } from '@/config/constants'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { services } from '@/services'
import { getErrorMessage } from '@/services/errors'
import type { ReportCategory } from '@/types/domain'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'
import { cn } from '@/utils/cn'

export function ReportDialog({
  open,
  onClose,
  reportedUid,
  reportedUsername,
}: {
  open: boolean
  onClose: () => void
  reportedUid: string
  reportedUsername: string
}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [category, setCategory] = useState<ReportCategory>('impersonation')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (!open) return
    setCategory('impersonation')
    setSubmitted(false)
    setError(null)
    setSubmitting(false)
  }, [open])

  const handleSubmit = async () => {
    if (!user) {
      navigate('/login', { state: { from: `/profile/${encodeURIComponent(reportedUsername)}` } })
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await services.reports.submitReport({ reportedUid, category })
      setSubmitted(true)
      toast({
        variant: 'success',
        title: 'Report submitted privately',
        description: 'An administrator will review it. The reported account is not automatically penalised.',
      })
    } catch (cause) {
      setError(getErrorMessage(cause))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Report @${reportedUsername}`}
      description="Reports are private. An administrator reviews them; submissions alone never automatically ban an account."
      footer={
        submitted ? (
          <div className="flex justify-end">
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        ) : (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} loading={submitting}>
              Submit report
            </Button>
          </div>
        )
      }
    >
      {!user ? (
        <Notice variant="info" title="Sign in required">
          You need an account to report a profile. Your username is shared with
          administrators, never with the reported user.
        </Notice>
      ) : submitted ? (
        <Notice variant="success" title="Thank you — the report is in the review queue">
          Administrators may remove content or contact the account. You will not
          receive public updates about the outcome.
        </Notice>
      ) : (
        <div className="space-y-4">
          <fieldset>
            <legend className="text-sm font-medium text-ink">What are you reporting?</legend>
            <div className="mt-3 space-y-2">
              {REPORT_CATEGORIES.map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition',
                    category === option.value
                      ? 'border-forest/40 bg-forest-tint/50'
                      : 'border-line bg-surface hover:border-forest/20',
                  )}
                >
                  <input
                    type="radio"
                    name="report-category"
                    value={option.value}
                    checked={category === option.value}
                    onChange={() => setCategory(option.value)}
                    className="mt-1 h-3.5 w-3.5 accent-forest"
                  />
                  <span>
                    <span className="block text-sm font-medium text-ink">{option.label}</span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-muted">
                      {option.description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <p className="text-[11px] leading-relaxed text-muted">
            To keep reports lightweight, no screenshots are attached and only the
            category is stored. Abuse of the report system can be reviewed by an
            administrator. In the Phase 1 demo this report is held in memory only.
          </p>

          {error ? <Notice variant="danger" title="Report not submitted">{error}</Notice> : null}
        </div>
      )}
    </Modal>
  )
}
