import { IST_TIMEZONE } from '@/types/domain'

/**
 * The competition runs Monday 00:00 IST → next Monday 00:00 IST.
 * India has no daylight saving, so a fixed UTC+05:30 offset is safe.
 */
export const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000
export const WEEK_MS = 7 * 24 * 60 * 60 * 1000

/** Shift a timestamp so its UTC fields read as IST wall-clock fields. */
function shiftToIst(date: Date): Date {
  return new Date(date.getTime() + IST_OFFSET_MS)
}

/** Monday 00:00 IST of the week containing `now`, expressed in UTC. */
export function getWeekStartIst(now: Date = new Date()): Date {
  const ist = shiftToIst(now)
  const dayOfWeek = ist.getUTCDay() // 0 = Sunday … 6 = Saturday
  const daysSinceMonday = (dayOfWeek + 6) % 7
  const startShifted = Date.UTC(
    ist.getUTCFullYear(),
    ist.getUTCMonth(),
    ist.getUTCDate() - daysSinceMonday,
  )
  return new Date(startShifted - IST_OFFSET_MS)
}

export function getCompetitionIdFor(start: Date): string {
  const ist = shiftToIst(start)
  const y = ist.getUTCFullYear()
  const m = String(ist.getUTCMonth() + 1).padStart(2, '0')
  const d = String(ist.getUTCDate()).padStart(2, '0')
  return `w${y}-${m}-${d}`
}

/** Derive the active weekly window from a trusted timestamp. */
export function getCompetitionWindow(now: Date = new Date()): {
  id: string
  startsAt: Date
  endsAt: Date
} {
  const startsAt = getWeekStartIst(now)
  return {
    id: getCompetitionIdFor(startsAt),
    startsAt,
    endsAt: new Date(startsAt.getTime() + WEEK_MS),
  }
}

const DAY = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST_TIMEZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const MONTH_SHORT = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST_TIMEZONE,
  month: 'short',
})

const DAY_NUM = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST_TIMEZONE,
  day: '2-digit',
})

const YEAR = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST_TIMEZONE,
  year: 'numeric',
})

const WEEKDAY_DATE = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST_TIMEZONE,
  weekday: 'short',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const TIME = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST_TIMEZONE,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatIstDate(iso: string | Date): string {
  return DAY.format(typeof iso === 'string' ? new Date(iso) : iso)
}

export function formatIstDateLong(iso: string | Date): string {
  return WEEKDAY_DATE.format(typeof iso === 'string' ? new Date(iso) : iso)
}

export function formatIstDateTime(iso: string | Date): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso
  return `${formatIstDateLong(date)}, ${TIME.format(date)} IST`
}

/** e.g. "19 – 25 OCT 2026", "26 OCT – 01 NOV 2026". */
export function formatWeekLabel(startsAt: string | Date): string {
  const start = typeof startsAt === 'string' ? new Date(startsAt) : startsAt
  const end = new Date(start.getTime() + WEEK_MS - 24 * 60 * 60 * 1000)
  const startDay = DAY_NUM.format(start)
  const endDay = DAY_NUM.format(end)
  const startMonth = MONTH_SHORT.format(start).toUpperCase()
  const endMonth = MONTH_SHORT.format(end).toUpperCase()
  const startYear = YEAR.format(start)
  const endYear = YEAR.format(end)

  if (startMonth === endMonth && startYear === endYear) {
    return `${startDay} – ${endDay} ${endMonth} ${endYear}`
  }
  if (startYear === endYear) {
    return `${startDay} ${startMonth} – ${endDay} ${endMonth} ${endYear}`
  }
  return `${startDay} ${startMonth} ${startYear} – ${endDay} ${endMonth} ${endYear}`
}

export interface CountdownParts {
  days: number
  hours: number
  minutes: number
  seconds: number
  totalMs: number
  expired: boolean
}

export function getCountdownParts(
  endsAt: string | Date,
  nowMs: number = Date.now(),
): CountdownParts {
  const end = (typeof endsAt === 'string' ? new Date(endsAt) : endsAt).getTime()
  const remaining = end - nowMs
  const totalMs = Math.max(0, remaining)
  const seconds = Math.floor(totalMs / 1000)
  return {
    days: Math.floor(seconds / 86400),
    hours: Math.floor((seconds % 86400) / 3600),
    minutes: Math.floor((seconds % 3600) / 60),
    seconds: seconds % 60,
    totalMs,
    expired: remaining <= 0,
  }
}

/** Two-digit countdown segment. */
export function padTime(value: number): string {
  return String(value).padStart(2, '0')
}

/** Short relative time, used in admin and moderation lists. */
export function formatRelativeTime(iso: string, nowMs: number = Date.now()): string {
  const then = new Date(iso).getTime()
  const diff = Math.max(0, nowMs - then)
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatIstDate(iso)
}
