import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import {
  CalendarDays,
  Crown,
  Flag,
  Lock,
  ShieldAlert,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { services } from '@/services'
import { useAuth } from '@/hooks/useAuth'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { PageHeader } from '@/components/ui/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Notice } from '@/components/ui/Notice'
import { ErrorState, LoadingState } from '@/components/ui/States'
import { RankTitleBadge } from '@/components/common/RankTitleBadge'
import { CompetitionCountdown } from '@/components/common/CompetitionCountdown'
import { Top10ShowcaseCard } from '@/components/profile/Top10ShowcaseCard'
import { ReportDialog } from '@/components/profile/ReportDialog'
import { RankingTitleNote } from '@/components/submission/RankingTitleNote'
import { EntertainmentDisclaimer } from '@/components/score/ScoreCard'
import { formatIstDate, formatIstDateTime } from '@/utils/datetime'

export function OwnProfileRedirect() {
  const { user, status } = useAuth()
  if (status === 'loading') {
    return (
      <div className="container-page py-24">
        <LoadingState label="Finding your profile…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={`/profile/${encodeURIComponent(user.username)}`} replace />
}

export function ProfilePage() {
  const { username = '' } = useParams()
  const { user } = useAuth()
  const profile = useAsync(() => services.profiles.getPublicProfile(username), [username])
  const leaderboard = useAsync(() => services.leaderboard.getLeaderboard(), [])
  const [reportOpen, setReportOpen] = useState(false)

  useDocumentTitle(
    profile.data ? `${profile.data.username}` : 'Profile',
  )

  const data = profile.data
  const isFirst = data?.rank === 1
  const isTopTen = data !== null && data?.rank != null && data.rank <= 10
  const competition = leaderboard.data?.competition ?? null

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="flex items-center gap-2">
            <Link to="/leaderboard" className="hover:text-ink">Leaderboard</Link>
            <span aria-hidden="true" className="text-line">/</span>
            <span>Participant profile</span>
          </span>
        }
        title={data ? data.username : 'Participant profile'}
        description="A public competition profile. It shows only what the leaderboard needs — never emails, tokens or moderation notes."
        actions={
          data && !data.isSelf ? (
            <button
              type="button"
              onClick={() => setReportOpen(true)}
              className="inline-flex h-9 items-center gap-1.5 rounded-field border border-line bg-surface px-3.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:border-danger/30 hover:text-danger"
            >
              <Flag className="h-3 w-3" aria-hidden="true" />
              Report profile
            </button>
          ) : null
        }
      />

      <div className="container-page py-8 lg:py-10">
        {profile.loading ? (
          <LoadingState label="Loading profile…" />
        ) : profile.error ? (
          <ErrorState
            title={
              profile.error.code === 'not-found'
                ? 'No participant with that username'
                : 'Profile unavailable'
            }
            message={profile.error.userMessage}
            code={profile.error.code}
            onRetry={profile.reload}
          />
        ) : data ? (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <div className="space-y-6">
              <section
                className="overflow-hidden rounded-card border border-line bg-surface"
                aria-label={`${data.username}'s competition profile`}
              >
                <div className="relative h-24 bg-forest-900 paper-texture sm:h-28">
                  <span
                    aria-hidden="true"
                    className="absolute right-5 top-1/2 -translate-y-1/2 font-serif text-5xl italic text-canvas/15 sm:text-6xl"
                  >
                    {data.rank !== null ? `#${data.rank}` : 'CHAD'}
                  </span>
                  {isTopTen ? (
                    <span className="absolute left-5 top-1/2 -translate-y-1/2">
                      <RankTitleBadge title={data.title} />
                    </span>
                  ) : null}
                </div>
                <div className="px-5 pb-6 sm:px-7">
                  <div className="-mt-12 flex flex-wrap items-end justify-between gap-4">
                    <ProfileAvatar
                      username={data.username}
                      imagePath={data.profileImagePath}
                      size="xl"
                      ring={isTopTen ? 'gold' : 'forest'}
                      className="border-4 border-surface"
                    />
                    <div className="flex flex-wrap gap-2 pb-1">
                      {data.isSelf ? (
                        <>
                          <ButtonLink to="/dashboard" variant="secondary" size="sm">
                            Dashboard
                          </ButtonLink>
                          {isTopTen && !data.showcase ? (
                            <ButtonLink to="/showcase" size="sm" icon={<Sparkles className="h-3.5 w-3.5" aria-hidden="true" />}>
                              Set up showcase
                            </ButtonLink>
                          ) : null}
                        </>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <h2 className="font-display text-2xl font-semibold tracking-tight text-ink">
                      {data.username}
                    </h2>
                    {data.isSelf ? <Badge variant="forest">You</Badge> : null}
                    <RankTitleBadge title={data.title} />
                  </div>

                  <div className="mt-5 grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">
                        Current rank
                      </p>
                      <p className="mt-1.5 font-display text-2xl font-semibold tabular-nums text-ink">
                        {data.rank !== null ? `#${data.rank}` : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">
                        Confirmed score
                      </p>
                      <p className="mt-1.5 font-display text-2xl font-semibold tabular-nums text-ink">
                        {data.score !== null ? (
                          <>
                            {data.score}
                            <span className="ml-0.5 text-[10px] font-normal text-muted">/100</span>
                          </>
                        ) : (
                          <span className="font-sans text-sm font-normal text-muted">
                            Not yet ranked
                          </span>
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">
                        Member since
                      </p>
                      <p className="mt-2 text-sm font-medium text-ink">
                        {formatIstDate(data.createdAt)}
                      </p>
                    </div>
                  </div>

                  {isFirst ? (
                    <div className="mt-6 flex flex-col gap-2 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-gold-deep">
                          <Crown className="h-3 w-3" aria-hidden="true" />
                          This week’s highest confirmed score
                        </p>
                        <p className="mt-1 font-serif text-3xl italic tracking-tight text-gold-deep sm:text-4xl">
                          True Adam
                        </p>
                      </div>
                      <span className="gold-rule sm:w-16" aria-hidden="true" />
                    </div>
                  ) : null}

                  {data.isSelf && !data.profileImagePath ? (
                    <p className="mt-5 text-[10px] leading-relaxed text-muted">
                      Profile picture placeholder. Permanent profile photos and square
                      cropping are part of Phase 2; the monogram stays until then.
                    </p>
                  ) : null}
                </div>
              </section>

              {data.accountStatus === 'suspended' ? (
                <Notice variant="danger" title="Account not active">
                  This account is suspended. Its score, rank and showcase are hidden
                  from public view while an administrator reviews it.
                </Notice>
              ) : null}

              {isTopTen ? (
                data.showcase ? (
                  <Top10ShowcaseCard username={data.username} showcase={data.showcase} />
                ) : (
                  <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
                    <div className="flex items-start gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gold-tint text-gold-deep">
                        <Sparkles className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <div>
                        <p className="eyebrow !text-gold-deep">Top 10 showcase</p>
                        <h2 className="mt-1.5 font-display text-lg font-semibold text-ink">
                          No showcase submitted yet.
                        </h2>
                        <p className="mt-1.5 text-sm leading-relaxed text-muted">
                          {data.isSelf
                            ? 'You are eligible this week. You can add an optional slogan and one photograph before the week closes.'
                            : 'This participant has not added a slogan or showcase photograph for this week.'}
                        </p>
                        {data.isSelf ? (
                          <ButtonLink to="/showcase" size="sm" className="mt-4">
                            Compose showcase
                          </ButtonLink>
                        ) : null}
                      </div>
                    </div>
                  </section>
                )
              ) : (
                <section className="rounded-card border border-line bg-canvas/60 p-5 sm:p-6">
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-subtle text-muted">
                      <Lock className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <div>
                      <p className="eyebrow">Showcase</p>
                      <h2 className="mt-1.5 font-display text-base font-semibold text-ink">
                        Reserved for the current Top 10.
                      </h2>
                      <p className="mt-1.5 text-sm leading-relaxed text-muted">
                        Showcase slogans and photographs are shown only while a
                        participant is in the Top 10. No expired showcase content is
                        displayed.
                      </p>
                    </div>
                  </div>
                </section>
              )}

              <EntertainmentDisclaimer />
            </div>

            <aside className="space-y-5">
              <div className="rounded-card border border-line bg-surface p-5">
                <p className="eyebrow">This week</p>
                {competition ? (
                  <>
                    <p className="mt-2 font-display text-sm font-semibold text-ink">
                      {competition.weekLabel}
                    </p>
                    <p className="mt-1 flex items-center gap-1.5 text-[11px] text-muted">
                      <CalendarDays className="h-3 w-3" aria-hidden="true" />
                      {formatIstDate(competition.startsAt)} → {formatIstDate(competition.endsAt)}
                    </p>
                    <CompetitionCountdown
                      endsAt={competition.endsAt}
                      label="Closes in"
                      className="mt-4"
                    />
                    <p className="mt-3 text-[10px] text-muted">
                      {formatIstDateTime(competition.endsAt)} · Asia/Kolkata
                    </p>
                  </>
                ) : (
                  <p className="mt-2 text-xs leading-relaxed text-muted">
                    The active competition is unavailable in this build.
                  </p>
                )}
              </div>

              <div className="rounded-card border border-line bg-surface p-5">
                <p className="eyebrow">Profile rules</p>
                <ul className="mt-3 space-y-2.5 text-[11px] leading-relaxed text-muted">
                  <li className="flex gap-2">
                    <UserRound className="mt-0.5 h-3 w-3 shrink-0 text-forest" aria-hidden="true" />
                    One persistent username per account.
                  </li>
                  <li className="flex gap-2">
                    <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0 text-forest" aria-hidden="true" />
                    Reports are private and reviewed by a human.
                  </li>
                  <li className="flex gap-2">
                    <Lock className="mt-0.5 h-3 w-3 shrink-0 text-forest" aria-hidden="true" />
                    Weekly scores and showcases reset automatically.
                  </li>
                </ul>
                <Link
                  to="/rules"
                  className="mt-4 inline-block text-[10px] font-medium text-forest underline underline-offset-2"
                >
                  Read full rules
                </Link>
              </div>

              <RankingTitleNote />

              {!data.isSelf && user ? (
                <button
                  type="button"
                  onClick={() => setReportOpen(true)}
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-field border border-line bg-surface px-3 py-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:border-danger/30 hover:text-danger"
                >
                  <Flag className="h-3 w-3" aria-hidden="true" />
                  Report this profile
                </button>
              ) : null}
            </aside>
          </div>
        ) : null}
      </div>

      {data && !data.isSelf ? (
        <ReportDialog
          open={reportOpen}
          onClose={() => setReportOpen(false)}
          reportedUid={data.uid}
          reportedUsername={data.username}
        />
      ) : null}
    </>
  )
}
