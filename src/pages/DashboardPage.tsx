import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  Camera,
  Crown,
  Lock,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { backendMode, services } from '@/services'
import type { ShowcaseEligibility, WeeklyStatus } from '@/types/domain'
import { PageHeader } from '@/components/ui/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { RankTitleBadge } from '@/components/common/RankTitleBadge'
import { CompetitionCountdown } from '@/components/common/CompetitionCountdown'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { Notice } from '@/components/ui/Notice'
import { Badge } from '@/components/ui/Badge'
import { BackendBanner, SampleDataTag } from '@/components/common/BackendBanner'
import { EntertainmentDisclaimer } from '@/components/score/ScoreCard'
import { formatIstDate, formatIstDateTime } from '@/utils/datetime'

function Card({
  eyebrow,
  title,
  action,
  children,
  className = '',
}: {
  eyebrow?: string
  title?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-card border border-line bg-surface ${className}`}>
      {(eyebrow || title || action) && (
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4 sm:px-6">
          <div>
            {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
            {title ? (
              <h2 className="mt-1.5 font-display text-base font-semibold text-ink">{title}</h2>
            ) : null}
          </div>
          {action}
        </div>
      )}
      <div className="p-5 sm:p-6">{children}</div>
    </section>
  )
}

function WeeklyStatusPanel({
  status,
  userEmailNote,
}: {
  status: WeeklyStatus
  userEmailNote: string
}) {
  const confirmed = status.submission?.status === 'confirmed'
  const submission = status.submission

  if (confirmed && submission?.confirmedScore !== null && submission) {
    return (
      <div>
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">This week’s confirmed result</p>
            <p className="mt-3 flex items-baseline gap-2">
              <span className="font-display text-5xl font-semibold leading-none tabular-nums tracking-[-0.04em] text-ink sm:text-6xl">
                {submission.confirmedScore}
              </span>
              <span className="font-serif text-lg italic text-muted">/ 100</span>
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Badge variant="success" icon={<Lock className="h-3 w-3" aria-hidden="true" />}>
                Confirmed &amp; locked
              </Badge>
              {status.title ? <RankTitleBadge title={status.title} /> : null}
            </div>
          </div>
          <div className="sm:text-right">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
              Current rank
            </p>
            <p className="mt-1 font-display text-3xl font-semibold tabular-nums text-ink">
              {status.rank !== null ? `#${status.rank}` : '—'}
            </p>
            <Link
              to="/leaderboard"
              className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-forest hover:underline underline-offset-4"
            >
              View board
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <p className="text-[11px] text-muted">
            Submitted {submission.submittedAt ? formatIstDateTime(submission.submittedAt) : '—'}.
            Locked until the weekly reset.
          </p>
          <Link
            to="/rules#competition"
            className="text-[11px] font-medium text-forest underline underline-offset-2"
          >
            Reset {formatIstDateTime(status.competition.endsAt)}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div>
      {status.blockedReason ? (
        <Notice variant="warning" title="You cannot enter this week" className="mb-5">
          {status.blockedReason}
        </Notice>
      ) : null}
      <EmptyState
        icon={Camera}
        title="You have not entered this week."
        description={
          <>
            Capture exactly three photos. Review your provisional entertainment
            score, retry if you want, then post one confirmed result.
            <span className="mt-2 block text-[11px] text-muted">{userEmailNote}</span>
          </>
        }
        action={
          status.canSubmit ? (
            <ButtonLink to="/submit" icon={<Camera className="h-4 w-4" aria-hidden="true" />}>
              Start this week’s submission
            </ButtonLink>
          ) : (
            <ButtonLink to="/leaderboard" variant="secondary">
              View this week’s board
            </ButtonLink>
          )
        }
        className="border-0 bg-transparent px-0 py-4"
      />
    </div>
  )
}

export function DashboardPage() {
  useDocumentTitle('Dashboard')
  const { user } = useAuth()

  const weekly = useAsync(
    () => services.submissions.getWeeklyStatus(user?.uid ?? ''),
    [user?.uid],
  )
  const leaderboard = useAsync(() => services.leaderboard.getLeaderboard(), [])
  const eligibility = useAsync<ShowcaseEligibility | null>(
    async () => {
      const status = weekly.data
      if (!status || status.rank === null || status.rank > 10) return null
      return services.showcases.getEligibility()
    },
    [weekly.data?.rank, weekly.data?.submission?.status],
  )

  if (!user) return null

  const status = weekly.data
  const competition = leaderboard.data?.competition ?? status?.competition ?? null
  const showcase = eligibility.data
  const isTopTen = status?.rank !== null && status?.rank !== undefined && status.rank <= 10

  return (
    <>
      <PageHeader
        eyebrow="Your dashboard"
        title={`Welcome back, ${user.username}.`}
        description={
          status
            ? `You are competing in the week of ${status.competition.weekLabel} (Asia/Kolkata). One confirmed score, locked until Monday 00:00 IST.`
            : 'Your weekly competition status, score and showcase access in one place.'
        }
        actions={
          <>
            <ButtonLink to="/leaderboard" variant="secondary" size="sm">
              Leaderboard
            </ButtonLink>
            {status?.canSubmit ? (
              <ButtonLink to="/submit" size="sm" icon={<Camera className="h-3.5 w-3.5" aria-hidden="true" />}>
                Enter this week
              </ButtonLink>
            ) : null}
          </>
        }
      />

      <div className="container-page py-8 lg:py-10">
        {backendMode !== 'demo' ? <BackendBanner className="mb-6" /> : null}
        {user.accountStatus === 'suspended' ? (
          <Notice variant="danger" title="Account suspended" className="mb-6">
            Your account is suspended. You can read the leaderboard and rules, but
            submissions and showcases are disabled. Contact an administrator for a
            review.
          </Notice>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="space-y-6">
            <Card
              eyebrow="This week"
              title="Your competition status"
              action={<SampleDataTag />}
            >
              {weekly.loading ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-40" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              ) : weekly.error ? (
                <ErrorState
                  message={weekly.error.userMessage}
                  code={weekly.error.code}
                  onRetry={weekly.reload}
                  title="Weekly status unavailable"
                  className="border-0 px-0 py-4"
                />
              ) : status ? (
                <WeeklyStatusPanel
                  status={status}
                  userEmailNote={
                    backendMode === 'demo'
                      ? 'Preview data only — nothing here is saved to a real backend.'
                      : 'Photos stay in browser memory; only the confirmed score is stored.'
                  }
                />
              ) : null}
            </Card>

            <Card
              eyebrow={isTopTen ? 'Top 10 privilege' : 'Showcase'}
              title={isTopTen ? 'Your exclusive showcase' : 'The Top 10 showcase'}
              action={
                isTopTen ? (
                  <Badge variant="gold" icon={<Crown className="h-3 w-3" aria-hidden="true" />}>
                    Eligible
                  </Badge>
                ) : null
              }
            >
              {eligibility.loading && isTopTen ? (
                <div className="space-y-3">
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ) : isTopTen ? (
                showcase?.showcase ? (
                  <div>
                    <p className="text-sm leading-relaxed text-muted">
                      Your slogan and showcase photograph are locked for this week and
                      will be removed at the weekly reset. Falling below rank 10 removes
                      them immediately.
                    </p>
                    {showcase.showcase.slogan ? (
                      <blockquote className="mt-4 border-l border-gold/50 pl-4 font-serif text-lg italic leading-relaxed text-ink">
                        “{showcase.showcase.slogan}”
                      </blockquote>
                    ) : null}
                    <div className="mt-5 flex flex-wrap gap-2">
                      <ButtonLink
                        to={`/profile/${encodeURIComponent(user.username)}`}
                        variant="secondary"
                        size="sm"
                      >
                        View public profile
                      </ButtonLink>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-start gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gold-tint text-gold-deep">
                        <Sparkles className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <div>
                        <p className="text-sm font-medium text-ink">
                          You are in this week’s Top 10.
                        </p>
                        <p className="mt-1 text-sm leading-relaxed text-muted">
                          Add an optional slogan and one showcase photograph. Both are
                          locked for the rest of the week once submitted.
                        </p>
                      </div>
                    </div>
                    <ButtonLink
                      to="/showcase"
                      size="sm"
                      className="mt-5"
                      icon={<ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />}
                    >
                      {showcase?.showcase ? 'Review showcase' : 'Set up showcase'}
                    </ButtonLink>
                  </div>
                )
              ) : (
                <div>
                  <p className="text-sm leading-relaxed text-muted">
                    Only the current Top 10 can publish a slogan and showcase
                    photograph. Eligibility is recalculated from confirmed scores — it
                    cannot be set from this browser.
                  </p>
                  <div className="mt-4 flex items-center gap-2 text-[11px] text-muted">
                    <ShieldCheck className="h-3.5 w-3.5 text-forest" aria-hidden="true" />
                    Top 10 badge, rank title and showcase unlock together.
                  </div>
                  <ButtonLink
                    to="/leaderboard"
                    variant="secondary"
                    size="sm"
                    className="mt-5"
                  >
                    See what it takes
                  </ButtonLink>
                </div>
              )}
            </Card>

            <Card eyebrow="The week" title="How scoring and resets work">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg border border-line bg-canvas/50 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                    Submission rules
                  </p>
                  <ul className="mt-3 space-y-2 text-xs leading-relaxed text-muted">
                    <li>Exactly three photos, analysed locally.</li>
                    <li>Retry before confirming; one score is posted.</li>
                    <li>Confirmed scores are locked until reset.</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-line bg-canvas/50 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                    Reset schedule
                  </p>
                  <ul className="mt-3 space-y-2 text-xs leading-relaxed text-muted">
                    <li>Scores and ranks reset weekly.</li>
                    <li>Showcase content is deleted, not archived.</li>
                    <li>Accounts and profile pictures persist.</li>
                  </ul>
                </div>
              </div>
              <EntertainmentDisclaimer className="mt-5" />
            </Card>
          </div>

          <aside className="space-y-6">
            <Card>
              <div className="flex items-center gap-3.5">
                <ProfileAvatar
                  username={user.username}
                  imagePath={user.profileImagePath}
                  size="lg"
                  ring={isTopTen ? 'gold' : 'forest'}
                />
                <div className="min-w-0">
                  <p className="truncate font-display text-lg font-semibold text-ink">
                    {user.username}
                  </p>
                  <p className="mt-1">
                    {status ? <RankTitleBadge title={status.title} /> : <RankTitleBadge title="NOT YET RANKED" />}
                  </p>
                </div>
              </div>

              <dl className="mt-5 space-y-3 border-t border-line pt-4 text-xs">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Rank</dt>
                  <dd className="font-medium text-ink">
                    {status?.rank !== null && status?.rank !== undefined ? `#${status.rank}` : 'Not ranked'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Confirmed score</dt>
                  <dd className="font-medium tabular-nums text-ink">
                    {status?.submission?.confirmedScore ?? '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Member since</dt>
                  <dd className="font-medium text-ink">{formatIstDate(user.createdAt)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Account</dt>
                  <dd className="font-medium capitalize text-ink">{user.role}</dd>
                </div>
              </dl>

              <div className="mt-5 grid gap-2">
                <ButtonLink
                  to={`/profile/${encodeURIComponent(user.username)}`}
                  variant="secondary"
                  size="sm"
                  fullWidth
                  icon={<UserRound className="h-3.5 w-3.5" aria-hidden="true" />}
                >
                  View public profile
                </ButtonLink>
                <p className="text-[10px] leading-relaxed text-muted">
                  Profile photo upload is part of Phase 2. Your monogram is used
                  until a permanent picture is uploaded.
                </p>
              </div>
            </Card>

            <Card eyebrow="Competition" title={competition ? competition.weekLabel : 'This week'}>
              {competition ? (
                <>
                  <div className="flex items-center gap-2 text-[11px] text-muted">
                    <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
                    {formatIstDate(competition.startsAt)} → {formatIstDate(competition.endsAt)}
                  </div>
                  <CompetitionCountdown
                    endsAt={competition.endsAt}
                    label="Competition ends in"
                    className="mt-5"
                  />
                  <div className="mt-5 flex items-center justify-between border-t border-line pt-4 text-[11px]">
                    <span className="text-muted">Confirmed participants</span>
                    <span className="font-semibold tabular-nums text-ink">
                      {leaderboard.data?.totalParticipants ?? '—'}
                    </span>
                  </div>
                  <p className="mt-3 text-[10px] leading-relaxed text-muted">
                    {formatIstDateTime(competition.endsAt)} · Asia/Kolkata
                  </p>
                </>
              ) : (
                <p className="text-xs leading-relaxed text-muted">
                  Competition timing is loaded from the backend and appears here once
                  it is configured.
                </p>
              )}
            </Card>
          </aside>
        </div>
      </div>
    </>
  )
}
