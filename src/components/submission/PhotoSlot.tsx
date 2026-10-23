import { Camera, RefreshCw, Trash2, Upload } from 'lucide-react'
import { cn } from '@/utils/cn'

export interface DraftPhoto {
  id: string
  file: File
  url: string
}

export function PhotoSlot({
  index,
  photo,
  onCamera,
  onUpload,
  onRemove,
  disabled,
}: {
  index: number
  photo: DraftPhoto | null
  onCamera: () => void
  onUpload: () => void
  onRemove: () => void
  disabled?: boolean
}) {
  return (
    <div className="min-w-0">
      <div
        className={cn(
          'group relative aspect-[3/4] overflow-hidden rounded-card border bg-surface',
          photo ? 'border-line' : 'border-dashed border-line',
        )}
      >
        {photo ? (
          <>
            <img
              src={photo.url}
              alt={`Captured photo ${index + 1}`}
              className="h-full w-full object-cover"
            />
            <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-2 bg-gradient-to-b from-black/45 to-transparent p-3">
              <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white/85">
                Photo {index + 1}
              </span>
              <span className="rounded-full bg-black/30 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-white/80">
                Local only
              </span>
            </div>
            <div className="absolute inset-x-0 bottom-0 flex gap-2 bg-gradient-to-t from-black/55 to-transparent p-3">
              <button
                type="button"
                onClick={onCamera}
                disabled={disabled}
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-white/95 px-2.5 py-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink transition hover:bg-white disabled:opacity-50"
              >
                <RefreshCw className="h-3 w-3" aria-hidden="true" />
                Retake
              </button>
              <button
                type="button"
                onClick={onRemove}
                disabled={disabled}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-black/35 text-white/90 transition hover:bg-black/55 disabled:opacity-50"
                aria-label={`Remove photo ${index + 1}`}
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center px-4 py-6 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-subtle text-muted">
              <Camera className="h-4 w-4" aria-hidden="true" />
            </span>
            <p className="mt-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink">
              Photo {index + 1}
            </p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              Three distinct photos are required.
            </p>
            <div className="mt-4 grid w-full gap-1.5">
              <button
                type="button"
                onClick={onCamera}
                disabled={disabled}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md bg-forest px-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-white transition hover:bg-forest-700 disabled:opacity-50"
              >
                <Camera className="h-3 w-3" aria-hidden="true" />
                Use camera
              </button>
              <button
                type="button"
                onClick={onUpload}
                disabled={disabled}
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-line bg-surface px-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:border-forest/25 hover:text-ink disabled:opacity-50"
              >
                <Upload className="h-3 w-3" aria-hidden="true" />
                Upload
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
