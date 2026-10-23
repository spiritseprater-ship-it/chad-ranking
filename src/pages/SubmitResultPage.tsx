import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  Crown,
  Lock,
  ShieldCheck,
  Sparkles,
  Trophy,
} from 'lucide-react'
import type {
  ConfirmSubmissionResult,
  ProvisionalScore,
  WeeklyStatus,
} from '@/types/domain'
import { backendMode, services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useSubmissionDraft } from '@/hooks/useSubmissionDraft'
import { getErrorMessage, isAppError } from '@/services/errors'
import { PageHeader } from '@/components/ui/PageHeader'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'
import { ConfirmDialog } from '@/components/ui/Modal'
import { EmptyState, Skeleton } from '@/components/ui/States'
import { ScoreCard, EntertainmentDisclaimer } from '@/components/score/ScoreCard'
import { RankTitleBadge } from '@/components/common/RankTitleBadge'
import { SubmissionSteps } from '@/components/submission/SubmissionSteps'
import { Badge } from '@/components/ui/Badge'
import { formatIstDateTime } from '@/utils/datetime'

interface PostedResult {
  result: ConfirmSubmissionResult
  provisional: ProvisionalScore
}

function EligibleConfirmation({ posted }: { posted: PostedResult }) {
  const { result } = posted
  const isFirst = result.rank === 1
  return (
    <div className="mx-auto max-w-3xl">
      <div className="relative overflow-hidden rounded-card border border-gold/40 bg-surface shadow-soft animate-pop">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold to-transparent" />
        <div className="px-6 py-10 text-center sm:px-12 sm:py-14">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-gold-tint text-gold-deep">
            <Crown className="h-5 w-5" aria-hidden="true" />
          </span>
          <p className="eyebrow mt-5 !text-gold-deep">Congratulations</p>
          <h1 className="mt-3 font-display text-3xl font-semibold tracking-[-0.025em] text-ink sm:text-[2.6rem]">
            You’ve entered the Top 10.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Your score is confirmed. The exclusive showcase is now available for
            this week.
          </p>

          <div className="mx-auto mt-8 grid max-w-md grid-cols-2 divide-x divide-line rounded-lg border border-line">
            <div className="px-5 py-5">
              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">
                Your rank
              </p>
              <p className="mt-1.5 font-display text-3xl font-semibold tabular-nums text-ink">
                #{result.rank}
              </p>
            </div>
            <div className="px-5 py-5">
              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">
                Chad score
              </p>
              <p className="mt-1.5 font-display text-3xl font-semibold tabular-nums text-ink">
                {result.score}
                <span className="ml-0.5 text-xs font-normal text-muted">/100</span>
              </p>
            </div>
          </div>

          <div className="mt-5 flex justify-center">
            <RankTitleBadge title={result.title} />
          </div>

          {isFirst ? (
            <p className="mt-6 font-serif text-3xl italic tracking-tight text-gold-deep sm:text-4xl">
              True Adam
            </p>
          ) : null}

          <div className="mt-8 flex flex-col justify-center gap-2 sm:flex-row">
            <ButtonLink to="/showcase" size="lg" icon={<Sparkles className="h-4 w-4" aria-hidden="true" />}>
              Set up your showcase
            </ButtonLink>
            <ButtonLink to="/leaderboard" variant="secondary" size="lg">
              View leaderboard
            </ButtonLink>
          </div>
          <p className="mt-5 text-[10px] leading-relaxed text-muted">
            You may submit a slogan and one showcase photograph. Once submitted, the
            showcase is locked for the rest of the week and removed if you leave the
            Top 10.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <EntertainmentDisclaimer />
      </div>
    </div>
  )
}

function PostedConfirmation({ posted }: { posted: PostedResult }) {
  const { result, provisional } = posted
  return (
    <div className="mx-auto max-w-2xl">
      <div className="rounded-card border border-line bg-surface px-6 py-9 text-center sm:px-10">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10 text-success">
          <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="eyebrow mt-5">Confirmed</p>
        <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          Your score is on the board.
        </h1>
        <div className="mx-auto mt-7 grid max-w-sm grid-cols-2 divide-x divide-line rounded-lg border border-line">
          <div className="px-4 py-4">
            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Rank</p>
            <p className="mt-1 font-display text-2xl font-semibold tabular-nums text-ink">
              #{result.rank}
            </p>
          </div>
          <div className="px-4 py-4">
            <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Score</p>
            <p className="mt-1 font-display text-2xl font-semibold tabular-nums text-ink">
              {result.score}
              <span className="ml-0.5 text-[10px] font-normal text-muted">/100</span>
            </p>
          </div>
        </div>
        <p className="mx-auto mt-5 max-w-md text-sm leading-relaxed text-muted">
          {result.rank <= 100
            ? 'You are inside the official Top 100 this week.'
            : 'You are outside the Top 100, so you appear in the participant directory by username only.'}{' '}
          Your score is locked until {formatIstDateTime(result.lockedUntil)}.
        </p>
        <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
          <ButtonLink to="/leaderboard" size="md">
            View leaderboard
          </ButtonLink>
          <ButtonLink to="/dashboard" variant="secondary" size="md">
            Go to dashboard
          </ButtonLink>
        </div>
      </div>

      <div className="mt-5">
        <ScoreCard
          score={provisional.total}
          label="Confirmed chad score"
          breakdown={provisional.breakdown}
          caption="This is the result posted for this competition week."
        />
      </div>
      <div className="mt-4">
        <EntertainmentDisclaimer />
      </div>
    </div>
  )
}

export function SubmitResultPage() {
  useDocumentTitle('Review your score')
  const navigate = useNavigate()
  const { user } = useAuth()
  const { draft, clearDraft } = useSubmissionDraft()
  const weekly = useAsync(
    () => services.submissions.getWeeklyStatus(user?.uid ?? ''),
    [user?.uid],
  )

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [alreadyConfirmed, setAlreadyConfirmed] = useState<WeeklyStatus | null>(null)
  const [posted, setPosted] = useState<PostedResult | null>(null)

  useEffect(() => {
    if (weekly.data?.submission?.status === 'confirmed' && !posted) {
      setAlreadyConfirmed(weekly.data)
    }
  }, [weekly.data, posted])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [posted])

  if (!user) return null

  if (posted?.result.showcaseEligible) {
    return (
      <div className="container-page py-10 sm:py-14">
        <EligibleConfirmation posted={posted} />
      </div>
    )
  }

  if (posted) {
    return (
      <div className="container-page py-10 sm:py-14">
        <PostedConfirmation posted={posted} />
      </div>
    )
  }

  if (alreadyConfirmed && !draft) {
    return (
      <div className="container-page py-16">
        <div className="mx-auto max-w-lg rounded-card border border-line bg-surface px-6 py-10 text-center">
          <Lock className="mx-auto h-6 w-6 text-muted" aria-hidden="true" />
          <h1 className="mt-4 font-display text-xl font-semibold text-ink">
            Your score is already confirmed.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            {alreadyConfirmed.submission?.confirmedScore ?? '—'} / 100 · Rank{' '}
            {alreadyConfirmed.rank !== null ? `#${alreadyConfirmed.rank}` : '—'}. Your
            entry is locked until the weekly reset.
          </p>
          <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
            <ButtonLink to="/leaderboard" size="sm">
              View leaderboard
            </ButtonLink>
            <ButtonLink to="/dashboard" variant="secondary" size="sm">
              Dashboard
            </ButtonLink>
          </div>
        </div>
      </div>
    )
  }

  if (!draft) {
    return (
      <div className="container-page py-16">
        <EmptyState
          icon={Trophy}
          title="No provisional result to review."
          description="Capture three photos first; the provisional score is held in browser memory only and disappears on refresh."
          action={<ButtonLink to="/submit">Start a submission</ButtonLink>}
          className="mx-auto max-w-lg"
        />
      </div>
    )
  }

  const handleConfirm = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const result = await services.submissions.confirmSubmission({
        competitionId: draft.competitionId,
        score: draft.provisional.total,
        scoringVersion: draft.provisional.scoringVersion,
        analyzedAt: draft.provisional.analyzedAt,
      })
      setPosted({ result, provisional: draft.provisional })
      setConfirmOpen(false)
      clearDraft()
    } catch (cause) {
      setConfirmOpen(false)
      if (isAppError(cause) && cause.code === 'already-confirmed') {
        if (weekly.data) setAlreadyConfirmed(weekly.data)
        else setError(cause.userMessage)
      } else {
        setError(
          isAppError(cause)
            ? cause.userMessage
            : getErrorMessage(cause),
        )
      }
    } finally {
      setSubmitting(false)
    }
  }

  const confirmLabel =
    backendMode === 'demo' ? 'Confirm & post (preview)' : 'Confirm & post'

  return (
    <>
      <PageHeader
        eyebrow="Score review"
        title="Your result is ready."
        description="Review the provisional result before submitting it to this week’s competition. Nothing is public yet."
        actions={
          <ButtonLink to="/submit" variant="secondary" size="sm">
            Back to photos
          </ButtonLink>
        }
      />

      <div className="container-page py-8 lg:py-10">
        <div className="mb-8 rounded-card border border-line bg-surface px-4 py-4 sm:px-6">
          <SubmissionSteps current={2} />
        </div>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-10">
          <div>
            <ScoreCard
              score={draft.provisional.total}
              label="Provisional score"
              title={
                draft.provisional.total >= 90
                  ? 'A high standard'
                  : draft.provisional.total >= 80
                    ? 'A strong week'
                    : 'Room to climb'
              }
              breakdown={draft.provisional.breakdown}
              caption={
                <>
                  Calculated in your browser from three temporary photographs.{' '}
                  {backendMode === 'demo'
                    ? 'This preview does not upload them.'
                    : 'The backend re-checks the submission before it becomes official.'}
                </>
              }
              footer={
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-[11px] leading-relaxed text-muted">
                    Provisional result · not public
                  </p>
                  <p className="text-[11px] text-muted">
                    Scoring version{' '}
                    <span className="font-mono text-[10px] text-ink">
                      {draft.provisional.scoringVersion}
                    </span>
                  </p>
                </div>
              }
            />

            {error ? (
              <Notice variant="danger" title="Score not confirmed" className="mt-5">
                {error}
                <p className="mt-2 text-[11px]">
                  Your score is not counted until a trusted confirmation succeeds.
                </p>
              </Notice>
            ) : null}

            {alreadyConfirmed ? (
              <Notice variant="warning" title="This week is already confirmed" className="mt-5">
                A confirmed score already exists. Only an administrator can correct
                it. Nothing was posted twice.
              </Notice>
            ) : null}

            <div className="mt-6 flex flex-col gap-2 sm:flex-row">
              <Button
                size="lg"
                onClick={() => setConfirmOpen(true)}
                disabled={submitting || Boolean(alreadyConfirmed)}
                loading={submitting}
                icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
                className="flex-row-reverse"
              >
                {confirmLabel}
              </Button>
              <Button
                variant="secondary"
                size="lg"
                onClick={() => {
                  clearDraft()
                  navigate('/submit')
                }}
                disabled={submitting}
              >
                Try again
              </Button>
            </div>

            <p className="mt-3 text-[11px] leading-relaxed text-muted">
              Trying again discards this provisional photo set and score. Your three
              photos were already released from this page.
            </p>

            <div className="mt-6">
              <EntertainmentDisclaimer />
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-card border border-line bg-surface p-5">
              <p className="eyebrow">Before you confirm</p>
              <ul className="mt-4 space-y-3">
                {[
                  'One confirmed score per account, per week.',
                  'The score locks immediately and cannot be edited until the reset.',
                  'The Top 10 showcase is available only if your final rank is 10 or better.',
                  'Raw scoring photos are not stored.',
                ].map((item) => (
                  <li key={item} className="flex gap-2.5 text-xs leading-relaxed text-muted">
                    <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-forest" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-card border border-line bg-surface p-5">
              <p className="eyebrow">Environment</p>
              {backendMode === 'demo' ? (
                <Badge variant="gold" className="mt-3">Preview · sample data</Badge>
              ) : (
                <Badge variant="warning" className="mt-3">Backend pending</Badge>
              )}
              <p className="mt-3 text-[11px] leading-relaxed text-muted">
                {backendMode === 'demo'
                  ? 'Confirmation writes to an in-memory demo store. Reloading this tab resets it. It is not an official result.'
                  : 'Confirmation is disabled until the Phase 2 backend is connected.'}
              </p>
            </div>

            <div className="rounded-card border border-line bg-surface p-5">
              <p className="eyebrow">Week</p>
              {weekly.loading ? (
                <Skeleton className="mt-3 h-12 w-full" />
              ) : weekly.data ? (
                <div className="mt-3 space-y-2 text-[11px] text-muted">
                  <p className="font-medium text-ink">{weekly.data.competition.weekLabel}</p>
                  <p>Closes {formatIstDateTime(weekly.data.competition.endsAt)}</p>
                  <p>Timezone: Asia/Kolkata</p>
                </div>
              ) : (
                <p className="mt-3 text-[11px] leading-relaxed text-muted">
                  Competition timing is unavailable until the backend is connected.
                </p>
              )}
            </div>
          </aside>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleConfirm}
        title="Confirm your final score?"
        description={
          <>
            Posting locks <strong className="text-ink">{draft.provisional.total}/100</strong>{' '}
            for the rest of this week. Your three photos will be discarded, and you
            cannot submit again until the next competition.
          </>
        }
        confirmLabel="Confirm & post"
        loading={submitting}
      />
    </>
  )
}
