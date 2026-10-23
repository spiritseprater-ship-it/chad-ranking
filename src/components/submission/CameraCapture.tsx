import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CameraOff, Check, RefreshCw, Upload } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Notice } from '@/components/ui/Notice'

type CameraStatus = 'starting' | 'ready' | 'error'

function describeCameraError(error: unknown): string {
  if (!window.isSecureContext) {
    return 'Camera access requires a secure (HTTPS) page. The GitHub Pages deployment and localhost are secure; a plain HTTP preview is not.'
  }
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError' || error.name === 'SecurityError') {
      return 'Camera permission was denied. Allow camera access in your browser settings, or upload a photo instead.'
    }
    if (error.name === 'NotFoundError' || error.name === 'OverconstrainedError') {
      return 'No camera was found on this device. You can upload photos instead.'
    }
    if (error.name === 'NotReadableError' || error.name === 'AbortError') {
      return 'The camera is busy or unavailable. Close other apps using it, or upload a photo instead.'
    }
  }
  return 'The camera could not be started. Check permissions, or upload a photo instead.'
}

/**
 * Live capture using getUserMedia. Photos exist only in browser memory and are
 * never uploaded by this component.
 */
export function CameraCapture({
  open,
  index,
  onClose,
  onCapture,
  onUploadFallback,
}: {
  open: boolean
  index: number
  onClose: () => void
  onCapture: (file: File) => void
  onUploadFallback: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [status, setStatus] = useState<CameraStatus>('starting')
  const [error, setError] = useState<string | null>(null)
  const [captured, setCaptured] = useState<{ url: string; file: File } | null>(null)
  const [attempt, setAttempt] = useState(0)

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  useEffect(() => {
    if (!open) {
      stopStream()
      setCaptured((previous) => {
        if (previous) URL.revokeObjectURL(previous.url)
        return null
      })
      setStatus('starting')
      setError(null)
      return
    }

    let cancelled = false
    setStatus('starting')
    setError(null)

    const start = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setStatus('error')
        setError(
          'This browser does not support live camera capture. Upload a photo instead.',
        )
        return
      }
      if (!window.isSecureContext) {
        setStatus('error')
        setError(describeCameraError(null))
        return
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 1280 },
            height: { ideal: 1600 },
          },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => undefined)
        }
        setStatus('ready')
      } catch (cause) {
        if (cancelled) return
        setStatus('error')
        setError(describeCameraError(cause))
      }
    }

    void start()
    return () => {
      cancelled = true
      stopStream()
    }
  }, [open, attempt, stopStream])

  const takePhoto = () => {
    const video = videoRef.current
    if (!video || video.videoWidth === 0) return
    const maxEdge = 1600
    const scale = Math.min(1, maxEdge / Math.max(video.videoWidth, video.videoHeight))
    const width = Math.round(video.videoWidth * scale)
    const height = Math.round(video.videoHeight * scale)
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) return

    // Match the mirrored selfie preview so the saved photo feels natural.
    context.translate(width, 0)
    context.scale(-1, 1)
    context.drawImage(video, 0, 0, width, height)

    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const file = new File([blob], `chad-photo-${index + 1}.jpg`, {
          type: 'image/jpeg',
          lastModified: Date.now(),
        })
        setCaptured({ url: URL.createObjectURL(blob), file })
      },
      'image/jpeg',
      0.9,
    )
  }

  const retake = () => {
    setCaptured((previous) => {
      if (previous) URL.revokeObjectURL(previous.url)
      return null
    })
    setAttempt((value) => value + 1)
  }

  const usePhoto = () => {
    if (!captured) return
    onCapture(captured.file)
    URL.revokeObjectURL(captured.url)
    setCaptured(null)
    onClose()
  }

  const handleClose = () => {
    if (captured) URL.revokeObjectURL(captured.url)
    setCaptured(null)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={`Photo ${index + 1}`}
      description="Use good light, hold still, and keep the camera at eye level. Nothing is uploaded."
      size="lg"
      footer={
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              handleClose()
              onUploadFallback()
            }}
            icon={<Upload className="h-3.5 w-3.5" aria-hidden="true" />}
          >
            Upload instead
          </Button>
          {captured ? (
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={retake} icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}>
                Retake
              </Button>
              <Button size="sm" onClick={usePhoto} icon={<Check className="h-3.5 w-3.5" aria-hidden="true" />}>
                Use photo
              </Button>
            </div>
          ) : (
            <Button size="sm" onClick={takePhoto} disabled={status !== 'ready'} icon={<Camera className="h-3.5 w-3.5" aria-hidden="true" />}>
              Capture
            </Button>
          )}
        </div>
      }
    >
      <div className="overflow-hidden rounded-lg border border-line bg-forest-900">
        {captured ? (
          <img
            src={captured.url}
            alt={`Preview of photo ${index + 1}`}
            className="mx-auto max-h-[52vh] w-auto object-contain"
          />
        ) : (
          <div className="relative">
            <video
              ref={videoRef}
              playsInline
              muted
              autoPlay
              className="mx-auto max-h-[52vh] w-full origin-center -scale-x-100 object-contain"
            />
            {status !== 'ready' ? (
              <div className="absolute inset-0 flex min-h-56 flex-col items-center justify-center gap-3 bg-forest-900 p-6 text-center">
                {status === 'error' ? (
                  <CameraOff className="h-6 w-6 text-canvas/65" aria-hidden="true" />
                ) : (
                  <span className="h-5 w-5 animate-spin rounded-full border-2 border-canvas/25 border-t-canvas/80" aria-hidden="true" />
                )}
                <p className="max-w-sm text-xs leading-relaxed text-canvas/65">
                  {status === 'error' ? error : 'Requesting camera permission…'}
                </p>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {status === 'error' ? (
        <Notice variant="warning" title="Camera unavailable" className="mt-4">
          {error}
        </Notice>
      ) : (
        <p className="mt-3 text-[11px] leading-relaxed text-muted">
          The front camera is requested by default. If this device has no camera,
          use the upload option. On iPhone and Android, camera access works best
          in Safari or Chrome over HTTPS.
        </p>
      )}
    </Modal>
  )
}
