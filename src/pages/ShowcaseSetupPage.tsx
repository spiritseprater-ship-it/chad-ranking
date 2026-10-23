import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Camera,
  Image as ImageIcon,
  Lock,
  Quote,
  Sparkles,
  Trophy,
  X,
} from 'lucide-react'
import {
  ENTERTAINMENT_DISCLAIMER,
  SLOGAN_MAX_LENGTH,
  rankTitleFor,
  SHOWCASE_PHOTO_LIMIT_MB,
} from '@/config/constants'
import { backendMode, services } from '@/services'
import { useAuth } from '@/hooks/useAuth'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useToast } from '@/hooks/useToast'
import { getErrorMessage } from '@/services/errors'
import { PageHeader } from '@/components/ui/PageHeader'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Field, TextArea } from '@/components/ui/Form'
import { Notice } from '@/components/ui/Notice'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/States'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { RankTitleBadge } from '@/components/common/RankTitleBadge'
import { ShowcaseImagePlaceholder, Top10ShowcaseCard } from '@/components/profile/Top10ShowcaseCard'

const ACCEPTED = new Set(['image/jpeg', 'image/png', 'image/webp'])

export function ShowcaseSetupPage() {
  useDocumentTitle('Top 10 showcase')
  const { user } = useAuth()
  const { toast } = useToast()
  const eligibility = useAsync(() => services.showcases.getEligibility(), [])

  const [slogan, setSlogan] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(
    () => () => {
      if (imagePreview) URL.revokeObjectURL(imagePreview)
    },
    [imagePreview],
  )

  if (!user) return null

  const handleFile = (file: File | null) => {
    setFileError(null)
    if (!file) return
    if (!ACCEPTED.has(file.type)) {
      setFileError('Use a JPG, PNG or WebP image.')
      return
    }
    if (file.size > SHOWCASE_PHOTO_LIMIT_MB * 1024 * 1024) {
      setFileError(`The showcase photo must be under ${SHOWCASE_PHOTO_LIMIT_MB} MB.`)
      return
    }
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  const clearImage = () => {
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImagePreview(null)
    setImageFile(null)
    if (fileInput.current) fileInput.current.value = ''
  }

  const handleSubmit = async () => {
    setSubmitError(null)
    if (slogan.trim().length > SLOGAN_MAX_LENGTH) {
      setSubmitError(`Keep your slogan to ${SLOGAN_MAX_LENGTH} characters or fewer.`)
      return
    }
    setSubmitting(true)
    try {
      await services.showcases.submitShowcase({
        slogan: slogan.trim(),
        imageFile,
      })
      toast({
        variant: 'success',
        title: 'Showcase locked for this week',
        description:
          backendMode === 'demo'
            ? 'Preview only: stored in this browser tab, not uploaded to a backend.'
            : 'Your showcase is now public on your profile while you remain in the Top 10.',
      })
      clearImage()
      setSlogan('')
      eligibility.reload()
    } catch (cause) {
      setSubmitError(getErrorMessage(cause))
    } finally {
      setSubmitting(false)
    }
  }

  const data = eligibility.data
  const title = data?.rank ? rankTitleFor(data.rank) : 'TOP 10'

  return (
    <>
      <PageHeader
        eyebrow="Top 10 privilege"
        title="Your showcase."
        description="One slogan. One photograph. Shown on your public profile only while you remain in this week’s Top 10."
        actions={
          <ButtonLink to="/dashboard" variant="secondary" size="sm">
            Back to dashboard
          </ButtonLink>
        }
      />

      <div className="container-page py-8 lg:py-10">
        {eligibility.loading ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Skeleton className="h-96 rounded-card" />
            <Skeleton className="h-96 rounded-card" />
          </div>
        ) : eligibility.error ? (
          eligibility.error.code === 'not-eligible' ? (
            <EmptyState
              icon={Trophy}
              title="The showcase is reserved for the Top 10."
              description="Confirm a score this week. Eligibility is derived from the live ranking and cannot be granted from this page."
              action={
                <div className="flex flex-col gap-2 sm:flex-row">
                  <ButtonLink to="/submit" size="sm">Enter this week</ButtonLink>
                  <ButtonLink to="/leaderboard" variant="secondary" size="sm">
                    View leaderboard
                  </ButtonLink>
                </div>
              }
              className="mx-auto max-w-xl"
            />
          ) : (
            <ErrorState
              title="Showcase unavailable"
              message={eligibility.error.userMessage}
              code={eligibility.error.code}
              onRetry={eligibility.reload}
              className="mx-auto max-w-xl"
            />
          )
        ) : data && !data.eligible ? (
          <EmptyState
            icon={Trophy}
            title="You are outside the Top 10 this week."
            description={
              data.reason ??
              'Only the current Top 10 can publish a showcase. Keep competing to climb.'
            }
            action={
              <div className="flex flex-col gap-2 sm:flex-row">
                <ButtonLink to="/leaderboard" size="sm">View leaderboard</ButtonLink>
                <ButtonLink to="/dashboard" variant="secondary" size="sm">Dashboard</ButtonLink>
              </div>
            }
            className="mx-auto max-w-xl"
          />
        ) : data?.showcase ? (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <div>
              <Notice variant="success" title="Locked for this week" className="mb-5">
                Your showcase was submitted and is now visible on your public profile.
                Editing and replacement are disabled until the weekly reset. An
                administrator can remove inappropriate content.
              </Notice>
              <Top10ShowcaseCard username={user.username} showcase={data.showcase} />
              <div className="mt-5 flex flex-wrap gap-2">
                <ButtonLink to={`/profile/${encodeURIComponent(user.username)}`} variant="secondary">
                  View public profile
                </ButtonLink>
                <ButtonLink to="/leaderboard" variant="secondary">
                  Leaderboard
                </ButtonLink>
              </div>
            </div>
            <aside className="space-y-5">
              <div className="rounded-card border border-line bg-surface p-5">
                <p className="eyebrow">Locking rules</p>
                <ul className="mt-4 space-y-3 text-xs leading-relaxed text-muted">
                  <li className="flex gap-2.5">
                    <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-forest" aria-hidden="true" />
                    One submission per eligibility period.
                  </li>
                  <li className="flex gap-2.5">
                    <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-forest" aria-hidden="true" />
                    Leaving the Top 10 hides and deletes the showcase automatically.
                  </li>
                  <li className="flex gap-2.5">
                    <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-forest" aria-hidden="true" />
                    The weekly reset removes the slogan and photograph. No archive is kept.
                  </li>
                </ul>
              </div>
              <p className="text-[10px] leading-relaxed text-muted">{ENTERTAINMENT_DISCLAIMER}</p>
            </aside>
          </div>
        ) : data ? (
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:gap-10">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="gold" icon={<Sparkles className="h-3 w-3" aria-hidden="true" />}>
                  Eligible · Rank #{data.rank}
                </Badge>
                <RankTitleBadge title={title} />
              </div>

              <h2 className="mt-4 font-display text-xl font-semibold text-ink">
                Compose your showcase
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                Both fields are optional, but once submitted the whole showcase is
                locked for the week. You can submit only once per eligibility
                period.
              </p>

              <div className="mt-6 space-y-5 rounded-card border border-line bg-surface p-5 sm:p-6">
                <Field
                  id="showcase-slogan"
                  label="Personal slogan"
                  optional
                  hint={`${slogan.trim().length}/${SLOGAN_MAX_LENGTH} characters. Keep it short and clean.`}
                >
                  <TextArea
                    id="showcase-slogan"
                    value={slogan}
                    onChange={(event) => setSlogan(event.target.value.slice(0, SLOGAN_MAX_LENGTH))}
                    rows={3}
                    maxLength={SLOGAN_MAX_LENGTH}
                    placeholder="Born to lead, not to follow."
                  />
                </Field>

                <div>
                  <p className="text-sm font-medium text-ink">
                    Showcase photograph
                    <span className="ml-1.5 text-xs font-normal text-muted">(optional)</span>
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted">
                    JPG, PNG or WebP · up to {SHOWCASE_PHOTO_LIMIT_MB} MB. This is
                    separate from your profile picture.
                  </p>

                  {imagePreview ? (
                    <div className="mt-3 overflow-hidden rounded-lg border border-line">
                      <img
                        src={imagePreview}
                        alt="Showcase preview"
                        className="aspect-[4/3] w-full object-cover"
                      />
                      <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-2">
                        <p className="truncate text-[11px] text-muted">{imageFile?.name}</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={clearImage}
                          icon={<X className="h-3 w-3" aria-hidden="true" />}
                          className="!px-2"
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => fileInput.current?.click()}
                      className="mt-3 flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line bg-canvas/50 px-4 py-8 text-center transition hover:border-forest/30 hover:bg-canvas"
                    >
                      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-subtle text-muted">
                        <ImageIcon className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <span className="text-xs font-medium text-ink">Choose a photograph</span>
                      <span className="text-[10px] text-muted">Landscape works best</span>
                    </button>
                  )}
                  <input
                    ref={fileInput}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="sr-only"
                    aria-label="Upload showcase photograph"
                    onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
                  />
                  {fileError ? (
                    <p className="mt-2 text-xs font-medium text-danger" role="alert">
                      {fileError}
                    </p>
                  ) : null}
                </div>

                {backendMode === 'demo' ? (
                  <Notice variant="warning" title="Preview: the photo is not uploaded">
                    In this frontend preview the image is held in browser memory using
                    an object URL and disappears on reload. Phase 2 uploads a
                    compressed copy through a validated backend path.
                  </Notice>
                ) : null}

                {submitError ? (
                  <Notice variant="danger" title="Showcase not submitted">
                    {submitError}
                  </Notice>
                ) : null}

                <Notice variant="neutral" title="This locks immediately">
                  After submission you cannot edit or replace the slogan or photograph.
                  If you leave the Top 10, the showcase is hidden and its stored image
                  is deleted.
                </Notice>

                <Button
                  onClick={handleSubmit}
                  loading={submitting}
                  size="lg"
                  fullWidth
                  icon={<Lock className="h-4 w-4" aria-hidden="true" />}
                >
                  Submit &amp; lock showcase
                </Button>
              </div>
            </div>

            <aside>
              <p className="eyebrow">Live preview</p>
              <p className="mt-1.5 text-[11px] text-muted">
                This is how your public showcase will appear while you are eligible.
              </p>

              <div className="mt-4 overflow-hidden rounded-card border border-line bg-surface">
                <div className="relative overflow-hidden bg-forest-900">
                  {imagePreview ? (
                    <img
                      src={imagePreview}
                      alt=""
                      className="aspect-[4/3] w-full object-cover"
                    />
                  ) : (
                    <ShowcaseImagePlaceholder username={user.username} />
                  )}
                  <div className="absolute left-3 top-3">
                    <RankTitleBadge title={title} />
                  </div>
                </div>
                <div className="p-5">
                  <div className="flex items-center gap-3">
                    <ProfileAvatar username={user.username} size="sm" ring="gold" />
                    <div>
                      <p className="font-display text-sm font-semibold text-ink">
                        {user.username}
                      </p>
                      <p className="text-[10px] uppercase tracking-[0.12em] text-muted">
                        Rank #{data.rank} · {data.score ?? '—'}/100
                      </p>
                    </div>
                  </div>
                  {slogan.trim() ? (
                    <blockquote className="mt-4 border-l border-gold/50 pl-4">
                      <Quote className="mb-1 h-3 w-3 text-gold" aria-hidden="true" />
                      <p className="font-serif text-base italic leading-relaxed text-ink">
                        {slogan.trim()}
                      </p>
                    </blockquote>
                  ) : (
                    <p className="mt-4 text-xs text-muted">
                      Your slogan will appear here.
                    </p>
                  )}
                  <p className="mt-4 flex items-center gap-1.5 border-t border-line pt-3 text-[10px] uppercase tracking-[0.1em] text-muted">
                    <Camera className="h-3 w-3" aria-hidden="true" />
                    Preview · not yet public
                  </p>
                </div>
              </div>

              <div className="mt-4 rounded-card border border-line bg-canvas/60 p-5">
                <p className="eyebrow">Eligibility</p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted">
                  Ranked #{data.rank} for the week. Showcase access is recalculated
                  whenever the leaderboard changes. It is never stored locally as a
                  permission.
                </p>
                <p className="mt-2 text-[10px] text-muted">
                  Current showcase submission:{' '}
                  <span className="text-ink">{data.showcase ? 'locked' : 'none'}</span>
                </p>
                <Link
                  to="/rules#showcase"
                  className="mt-3 inline-flex items-center gap-1 text-[10px] font-medium text-forest underline underline-offset-2"
                >
                  Showcase rules
                  <ArrowRight className="h-3 w-3" aria-hidden="true" />
                </Link>
              </div>
            </aside>
          </div>
        ) : null}
      </div>
    </>
  )
}
