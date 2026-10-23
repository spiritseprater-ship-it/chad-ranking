import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  Camera,
  Info,
  Lock,
  ScanFace,
  ShieldCheck,
} from 'lucide-react'
import { SCORING_CATEGORIES, ENTERTAINMENT_DISCLAIMER } from '@/config/constants'
import { backendMode, services } from '@/services'
import { useAuth } from '@/hooks/useAuth'
import { useAsync } from '@/hooks/useAsync'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useSubmissionDraft } from '@/hooks/useSubmissionDraft'
import { analyzePhotoSet, validatePhotoFile } from '@/services/scoring/localScoring'
import { getErrorMessage, isAppError } from '@/services/errors'
import type { WeeklyStatus } from '@/types/domain'
import { PageHeader } from '@/components/ui/PageHeader'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'
import { Badge } from '@/components/ui/Badge'
import { ErrorState, Skeleton } from '@/components/ui/States'
import { PhotoSlot, type DraftPhoto } from '@/components/submission/PhotoSlot'
import { CameraCapture } from '@/components/submission/CameraCapture'
import { SubmissionSteps } from '@/components/submission/SubmissionSteps'
import { BackendBanner, SampleDataTag } from '@/components/common/BackendBanner'
import { RankingTitleNote } from '@/components/submission/RankingTitleNote'

const EMPTY_SLOTS: Array<DraftPhoto | null> = [null, null, null]

function BlockedPanel({ status }: { status: WeeklyStatus }) {
  const confirmed = status.submission?.status === 'confirmed'
  return (
    <div className="mx-auto max-w-xl rounded-card border border-line bg-surface px-6 py-10 text-center">
      <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-subtle text-muted">
        {confirmed ? (
          <Lock className="h-5 w-5" aria-hidden="true" />
        ) : (
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        )}
      </span>
      <h2 className="mt-5 font-display text-xl font-semibold text-ink">
        {confirmed ? 'Your week is already claimed.' : 'Submission unavailable'}
      </h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted">
        {status.blockedReason ?? 'You cannot submit an entry for this competition right now.'}
      </p>
      {confirmed && status.submission?.confirmedScore !== null ? (
        <p className="mt-5 font-display text-4xl font-semibold tabular-nums text-ink">
          {status.submission?.confirmedScore}
          <span className="ml-1 font-serif text-base font-normal italic text-muted">/ 100</span>
        </p>
      ) : null}
      <div className="mt-7 flex flex-col justify-center gap-2 sm:flex-row">
        <ButtonLink to="/dashboard" variant="primary" size="sm">
          Go to dashboard
        </ButtonLink>
        <ButtonLink to="/leaderboard" variant="secondary" size="sm">
          View leaderboard
        </ButtonLink>
      </div>
    </div>
  )
}

export function SubmitPage() {
  useDocumentTitle('Weekly submission')
  const { user } = useAuth()
  const navigate = useNavigate()
  const { setDraft } = useSubmissionDraft()
  const weekly = useAsync(
    () => services.submissions.getWeeklyStatus(user?.uid ?? ''),
    [user?.uid],
  )

  const [photos, setPhotos] = useState<Array<DraftPhoto | null>>(EMPTY_SLOTS)
  const [cameraIndex, setCameraIndex] = useState<number | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputs = useRef<Array<HTMLInputElement | null>>([])
  const liveUrls = useRef<Set<string>>(new Set())

  useEffect(
    () => () => {
      liveUrls.current.forEach((url) => URL.revokeObjectURL(url))
      liveUrls.current.clear()
    },
    [],
  )

  if (!user) return null

  const setSlot = (index: number, photo: DraftPhoto | null) => {
    setPhotos((current) => {
      const next = [...current]
      const previous = next[index]
      if (previous) {
        URL.revokeObjectURL(previous.url)
        liveUrls.current.delete(previous.url)
      }
      next[index] = photo
      return next
    })
  }

  const releaseAllPhotos = () => {
    setPhotos((current) => {
      current.forEach((photo) => {
        if (!photo) return
        URL.revokeObjectURL(photo.url)
        liveUrls.current.delete(photo.url)
      })
      return EMPTY_SLOTS
    })
  }

  const addPhoto = (index: number, file: File) => {
    try {
      validatePhotoFile(file)
      const url = URL.createObjectURL(file)
      liveUrls.current.add(url)
      setSlot(index, { id: `${Date.now()}-${index}`, file, url })
      setError(null)
    } catch (cause) {
      setError(isAppError(cause) ? cause.userMessage : getErrorMessage(cause))
    }
  }

  const handleFileChange = (index: number, fileList: FileList | null) => {
    const file = fileList?.[0]
    if (!file) return
    addPhoto(index, file)
    const input = fileInputs.current[index]
    if (input) input.value = ''
  }

  const filledPhotos = photos.filter((photo): photo is DraftPhoto => photo !== null)
  const complete = filledPhotos.length === 3

  const handleAnalyze = async () => {
    setError(null)
    const status = weekly.data
    if (!status) return
    if (!complete) {
      setError('Capture all three photos before analysing.')
      return
    }
    setAnalyzing(true)
    try {
      const provisional = await analyzePhotoSet(filledPhotos.map((photo) => photo.file))
      setDraft({
        provisional,
        competitionId: status.competition.id,
        photoCount: 3,
      })
      releaseAllPhotos()
      navigate('/submit/result')
    } catch (cause) {
      setError(isAppError(cause) ? cause.userMessage : getErrorMessage(cause))
    } finally {
      setAnalyzing(false)
    }
  }

  const status = weekly.data
  const blocked = Boolean(status && !status.canSubmit)

  return (
    <>
      <PageHeader
        eyebrow="Weekly entry"
        title="Three photos. One claim."
        description="Capture three distinct photos, review the provisional entertainment score, then confirm one result for this week. Retakes are allowed before you post."
        actions={
          <ButtonLink to="/rules#scoring" variant="secondary" size="sm">
            How scoring works
          </ButtonLink>
        }
      />

      <div className="container-page py-8 lg:py-10">
        {backendMode !== 'demo' ? <BackendBanner className="mb-6" /> : null}

        <div className="mb-8 rounded-card border border-line bg-surface px-4 py-4 sm:px-6">
          <SubmissionSteps current={1} />
        </div>

        {weekly.loading ? (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {[0, 1, 2].map((index) => (
                  <Skeleton key={index} className="aspect-[3/4] rounded-card" />
                ))}
              </div>
              <Skeleton className="h-12 w-full" />
            </div>
            <Skeleton className="h-72 rounded-card" />
          </div>
        ) : weekly.error ? (
          <ErrorState
            title="Weekly status unavailable"
            message={weekly.error.userMessage}
            code={weekly.error.code}
            onRetry={weekly.reload}
          />
        ) : blocked && status ? (
          <BlockedPanel status={status} />
        ) : (
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-10">
            <div>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="eyebrow">Photo set</p>
                    <SampleDataTag />
                  </div>
                  <h2 className="mt-2 font-display text-xl font-semibold text-ink">
                    Capture your three photos
                  </h2>
                </div>
                <p className="text-xs text-muted" aria-live="polite">
                  <span className="font-semibold text-ink">{filledPhotos.length}</span> of 3
                  captured
                </p>
              </div>

              <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
                {EMPTY_SLOTS.map((_, index) => (
                  <div key={index}>
                    <PhotoSlot
                      index={index}
                      photo={photos[index] ?? null}
                      onCamera={() => setCameraIndex(index)}
                      onUpload={() => fileInputs.current[index]?.click()}
                      onRemove={() => setSlot(index, null)}
                      disabled={analyzing}
                    />
                    <input
                      ref={(element) => {
                        fileInputs.current[index] = element
                      }}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="sr-only"
                      aria-label={`Upload photo ${index + 1}`}
                      onChange={(event) => handleFileChange(index, event.target.files)}
                    />
                  </div>
                ))}
              </div>

              <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Button
                  size="lg"
                  onClick={handleAnalyze}
                  loading={analyzing}
                  disabled={!complete}
                  icon={<ScanFace className="h-4 w-4" aria-hidden="true" />}
                >
                  Analyse my photos
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  onClick={releaseAllPhotos}
                  disabled={filledPhotos.length === 0 || analyzing}
                >
                  Clear all
                </Button>
                {!complete ? (
                  <p className="text-[11px] text-muted">
                    {3 - filledPhotos.length} more {3 - filledPhotos.length === 1 ? 'photo' : 'photos'} needed.
                  </p>
                ) : null}
              </div>

              {error ? (
                <Notice variant="danger" title="Check your photos" className="mt-5">
                  {error}
                  <p className="mt-2 text-[11px]">
                    You can retake an individual photo without losing the others.
                  </p>
                </Notice>
              ) : null}

              <Notice variant="info" title="What happens next" className="mt-6">
                Your browser analyses the three images locally and shows a provisional
                score. Nothing is public until you confirm. Confirmation requires the
                trusted backend; in this preview it is stored in browser memory.
              </Notice>

              <div className="mt-6 flex items-start gap-2.5 rounded-lg border border-line bg-subtle/40 px-4 py-3">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
                <p className="text-[11px] leading-relaxed text-muted">
                  Raw scoring photos are not uploaded to storage or written to the
                  database. They are released when you analyse, retake or leave this
                  page. Clearing browser memory is not equivalent to securely erasing
                  every possible device-level trace, and your browser or operating
                  system may cache files independently.
                </p>
              </div>
            </div>

            <aside className="space-y-5">
              <div className="rounded-card border border-line bg-surface p-5">
                <div className="flex items-center gap-2">
                  <Camera className="h-4 w-4 text-forest" aria-hidden="true" />
                  <p className="eyebrow !text-ink">Photo checklist</p>
                </div>
                <ul className="mt-4 space-y-3 text-xs leading-relaxed text-muted">
                  <li>Use three clearly different poses or angles.</li>
                  <li>Face a window or soft light — avoid harsh backlight.</li>
                  <li>Keep the camera steady and at eye level.</li>
                  <li>No filters or other people in the frame.</li>
                  <li>JPG, PNG or WebP up to 8 MB per photo.</li>
                </ul>
                <p className="mt-4 border-t border-line pt-3 text-[10px] leading-relaxed text-muted">
                  Camera access needs a secure HTTPS page. On desktop without a
                  camera, use the upload option.
                </p>
              </div>

              <div className="rounded-card border border-line bg-surface p-5">
                <div className="flex items-center justify-between gap-2">
                  <p className="eyebrow">Entertainment categories</p>
                  <Badge variant="outline" className="!text-[8px]">Not a rating</Badge>
                </div>
                <dl className="mt-4 space-y-3">
                  {SCORING_CATEGORIES.map((category) => (
                    <div key={category.category} className="flex items-start justify-between gap-3">
                      <div>
                        <dt className="text-xs font-medium text-ink">{category.label}</dt>
                        <dd className="mt-0.5 text-[10px] leading-relaxed text-muted">
                          {category.description}
                        </dd>
                      </div>
                      <span className="shrink-0 font-display text-xs font-semibold text-muted">
                        {Math.round(category.weight * 100)}%
                      </span>
                    </div>
                  ))}
                </dl>
                <p className="mt-4 text-[10px] leading-relaxed text-muted">
                  {ENTERTAINMENT_DISCLAIMER}
                </p>
              </div>

              <div className="rounded-card border border-line bg-surface p-5">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-forest" aria-hidden="true" />
                  <p className="eyebrow !text-ink">Weekly rules</p>
                </div>
                <ul className="mt-3 space-y-2 text-[11px] leading-relaxed text-muted">
                  <li>One confirmed score per week.</li>
                  <li>Retry freely before confirming.</li>
                  <li>Confirmed scores lock until reset.</li>
                  <li>
                    <Link to="/rules" className="font-medium text-forest underline underline-offset-2">
                      Full rules & privacy
                    </Link>
                  </li>
                </ul>
              </div>

              <RankingTitleNote />
            </aside>
          </div>
        )}
      </div>

      <CameraCapture
        open={cameraIndex !== null}
        index={cameraIndex ?? 0}
        onClose={() => setCameraIndex(null)}
        onCapture={(file) => {
          if (cameraIndex !== null) addPhoto(cameraIndex, file)
        }}
        onUploadFallback={() => {
          if (cameraIndex !== null) {
            const index = cameraIndex
            window.setTimeout(() => fileInputs.current[index]?.click(), 50)
          }
        }}
      />
    </>
  )
}
