import { ANALYSIS_PHOTO_LIMIT_MB, SCORING_CATEGORIES } from '@/config/constants'
import { AppError } from '@/services/errors'
import type { ProvisionalScore, ScoreBreakdownItem } from '@/types/domain'

/**
 * LOCAL ENTERTAINMENT SCORING — browser only, no AI service.
 *
 * This is deliberately a transparent, documented heuristic. It measures image
 * properties (lighting, contrast, colour, detail and the visual variety between
 * the three photos) — it does NOT assess faces, bodies, health or ethnicity,
 * and it is not a scientific measurement of anything.
 *
 * Formula (see docs/SCORING.md):
 *   pose        = 55 + 40 × clamp(variety / 0.12)
 *   expression  = 100 × (0.45·exposure + 0.35·contrast + 0.20·mid-tone balance)
 *   creativity  = 100 × (0.40·colour + 0.30·sharpness + 0.30·contrast)
 *   styling     = 100 × (0.60·palette consistency + 0.40·colour)
 *   CHAD SCORE  = round(30%·pose + 25%·expression + 25%·creativity + 20%·styling)
 *
 * No randomness is involved: the same three images always produce the same
 * score. Phase 2 will re-validate and confirm this score on the backend.
 */

export const SCORING_VERSION = 'local-heuristic-v1'
const SAMPLE_SIZE = 96
const ACCEPTED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

interface PhotoStats {
  brightness: number
  contrast: number
  sharpness: number
  saturation: number
  exposure: number
  palette: [number, number, number]
  luma: Float32Array
}

export interface AnalysisInput {
  file: File
}

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value))

export function validatePhotoFile(file: File): void {
  if (!ACCEPTED_TYPES.has(file.type)) {
    throw new AppError('invalid-image', {
      userMessage: 'Use JPG, PNG or WebP photos. Other formats cannot be analysed.',
    })
  }
  if (file.size > ANALYSIS_PHOTO_LIMIT_MB * 1024 * 1024) {
    throw new AppError('image-too-large', {
      userMessage: `Each photo must be under ${ANALYSIS_PHOTO_LIMIT_MB} MB.`,
    })
  }
}

async function decodeImage(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if ('createImageBitmap' in window) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch {
      // Fall through to the <img> decoder (older Safari, some formats).
    }
  }

  return new Promise<HTMLImageElement>((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(
        new AppError('analysis-failed', {
          userMessage: 'That photo could not be opened. Try a different image.',
        }),
      )
    }
    image.src = url
  })
}

function imageSize(image: ImageBitmap | HTMLImageElement): { width: number; height: number } {
  if (image instanceof HTMLImageElement) {
    return { width: image.naturalWidth, height: image.naturalHeight }
  }
  return { width: image.width, height: image.height }
}

async function collectStats(file: File): Promise<PhotoStats> {
  validatePhotoFile(file)
  const image = await decodeImage(file)
  const { width, height } = imageSize(image)
  if (width < SAMPLE_SIZE || height < SAMPLE_SIZE) {
    throw new AppError('analysis-failed', {
      userMessage: 'That photo is too small to read. Capture a larger photo and try again.',
    })
  }

  const side = Math.min(width, height)
  const sx = (width - side) / 2
  const sy = (height - side) / 2

  const canvas = document.createElement('canvas')
  canvas.width = SAMPLE_SIZE
  canvas.height = SAMPLE_SIZE
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) {
    throw new AppError('analysis-failed', {
      userMessage: 'Your browser could not process images. Try another browser.',
    })
  }
  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(image, sx, sy, side, side, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  if ('close' in image && typeof image.close === 'function') image.close()

  const { data } = context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  const luma = new Float32Array(SAMPLE_SIZE * SAMPLE_SIZE)

  let sumLuma = 0
  let sumSaturation = 0
  let sumR = 0
  let sumG = 0
  let sumB = 0
  let clipped = 0

  for (let i = 0; i < luma.length; i += 1) {
    const offset = i * 4
    const r = (data[offset] ?? 0) / 255
    const g = (data[offset + 1] ?? 0) / 255
    const b = (data[offset + 2] ?? 0) / 255
    const y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    luma[i] = y
    sumLuma += y
    sumR += r
    sumG += g
    sumB += b

    const max = Math.max(r, g, b)
    const min = Math.min(r, g, b)
    sumSaturation += max === 0 ? 0 : (max - min) / max
    if (y < 0.045 || y > 0.955) clipped += 1
  }

  const count = luma.length
  const brightness = sumLuma / count
  let variance = 0
  for (let i = 0; i < count; i += 1) {
    const delta = (luma[i] ?? 0) - brightness
    variance += delta * delta
  }
  const contrast = Math.min(1, Math.sqrt(variance / count) / 0.32)

  let gradientSum = 0
  let gradientCount = 0
  for (let y = 0; y < SAMPLE_SIZE; y += 1) {
    for (let x = 0; x < SAMPLE_SIZE; x += 1) {
      const index = y * SAMPLE_SIZE + x
      const here = luma[index] ?? 0
      if (x + 1 < SAMPLE_SIZE) {
        gradientSum += Math.abs(here - (luma[index + 1] ?? here))
        gradientCount += 1
      }
      if (y + 1 < SAMPLE_SIZE) {
        gradientSum += Math.abs(here - (luma[index + SAMPLE_SIZE] ?? here))
        gradientCount += 1
      }
    }
  }
  const sharpness = Math.min(1, gradientSum / Math.max(1, gradientCount) / 0.075)

  return {
    brightness,
    contrast,
    sharpness,
    saturation: Math.min(1, sumSaturation / count / 0.45),
    exposure: 1 - clipped / count,
    palette: [sumR / count, sumG / count, sumB / count],
    luma,
  }
}

function meanAbsDifference(a: Float32Array, b: Float32Array): number {
  let total = 0
  const length = Math.min(a.length, b.length)
  for (let i = 0; i < length; i += 1) {
    total += Math.abs((a[i] ?? 0) - (b[i] ?? 0))
  }
  return total / Math.max(1, length)
}

function paletteConsistency(stats: PhotoStats[]): number {
  const channels = [0, 1, 2] as const
  let spread = 0
  for (const channel of channels) {
    const values = stats.map((stat) => stat.palette[channel])
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length
    const variance =
      values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length
    spread += Math.sqrt(variance)
  }
  return clamp01(1 - spread / 0.28)
}

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / Math.max(1, values.length)
}

function buildBreakdown(categoryScores: Record<(typeof SCORING_CATEGORIES)[number]['category'], number>): {
  breakdown: ScoreBreakdownItem[]
  total: number
} {
  const breakdown = SCORING_CATEGORIES.map((definition) => ({
    category: definition.category,
    label: definition.label,
    weight: definition.weight,
    score: Math.round(categoryScores[definition.category]),
    description: definition.description,
  }))
  const weighted = breakdown.reduce((sum, item) => sum + item.score * item.weight, 0)
  return { breakdown, total: Math.max(0, Math.min(100, Math.round(weighted))) }
}

export async function analyzePhotoSet(files: File[]): Promise<ProvisionalScore> {
  if (files.length !== 3) {
    throw new AppError('analysis-failed', {
      userMessage: 'Exactly three photos are required for a complete submission.',
    })
  }

  let stats: PhotoStats[]
  try {
    stats = await Promise.all(files.map(collectStats))
  } catch (error) {
    if (error instanceof AppError) throw error
    throw new AppError('analysis-failed', {
      message: error instanceof Error ? error.message : 'image decode failed',
    })
  }

  // Quality gate: ask for a retake instead of inventing a score.
  if (stats.some((stat) => stat.brightness < 0.08)) {
    throw new AppError('analysis-failed', {
      userMessage: 'One of your photos is too dark to read. Move somewhere brighter and retake it.',
    })
  }
  if (stats.some((stat) => stat.brightness > 0.94)) {
    throw new AppError('analysis-failed', {
      userMessage: 'One of your photos is overexposed. Avoid pointing the camera at a bright light.',
    })
  }
  if (stats.some((stat) => stat.sharpness < 0.06)) {
    throw new AppError('analysis-failed', {
      userMessage: 'One of your photos looks blurry. Hold still and retake it.',
    })
  }

  const differences = [
    meanAbsDifference(stats[0]!.luma, stats[1]!.luma),
    meanAbsDifference(stats[1]!.luma, stats[2]!.luma),
    meanAbsDifference(stats[0]!.luma, stats[2]!.luma),
  ]
  if (Math.min(...differences) < 0.004) {
    throw new AppError('analysis-failed', {
      userMessage: 'Two of your photos look identical. Take three distinct poses and try again.',
    })
  }

  const variety = clamp01(mean(differences) / 0.12)
  const exposure = clamp01(mean(stats.map((stat) => stat.exposure)))
  const contrast = clamp01(mean(stats.map((stat) => stat.contrast)))
  const colour = clamp01(mean(stats.map((stat) => stat.saturation)))
  const sharpness = clamp01(mean(stats.map((stat) => stat.sharpness)))
  const midTone = clamp01(
    1 - Math.abs(mean(stats.map((stat) => stat.brightness)) - 0.55) / 0.4,
  )
  const consistency = paletteConsistency(stats)

  const pose = 55 + 40 * variety
  const expression = 100 * (0.45 * exposure + 0.35 * contrast + 0.2 * midTone)
  const creativity = 100 * (0.4 * colour + 0.3 * sharpness + 0.3 * contrast)
  const styling = 100 * (0.6 * consistency + 0.4 * colour)

  const { breakdown, total } = buildBreakdown({
    pose,
    expression,
    creativity,
    styling,
  })

  return {
    total,
    breakdown,
    scoringVersion: SCORING_VERSION,
    method: 'browser-heuristic',
    analyzedAt: new Date().toISOString(),
  }
}
