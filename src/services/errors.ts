export type AppErrorCode =
  | 'backend-unconfigured'
  | 'not-implemented'
  | 'invalid-credentials'
  | 'username-taken'
  | 'username-invalid'
  | 'email-in-use'
  | 'weak-password'
  | 'not-authenticated'
  | 'forbidden'
  | 'not-found'
  | 'competition-expired'
  | 'already-confirmed'
  | 'not-eligible'
  | 'showcase-locked'
  | 'analysis-failed'
  | 'invalid-image'
  | 'image-too-large'
  | 'rate-limited'
  | 'duplicate-report'
  | 'network'
  | 'quota'
  | 'unknown'

const FRIENDLY: Record<AppErrorCode, string> = {
  'backend-unconfigured':
    'The backend is not configured in this build. Follow the Firebase setup steps in the README, then reload.',
  'not-implemented':
    'This action is part of Phase 2 and is not connected to a backend yet. Nothing was saved.',
  'invalid-credentials': 'That username or password does not match an account.',
  'username-taken': 'That username is already taken. Try another one.',
  'username-invalid': 'That username does not meet the rules.',
  'email-in-use': 'An account already exists for that email address.',
  'weak-password': 'Choose a stronger password with at least 8 characters and a number.',
  'not-authenticated': 'Please log in to continue.',
  forbidden: 'You do not have permission to do that.',
  'not-found': 'We could not find what you were looking for.',
  'competition-expired':
    'This week’s competition has closed. The next competition starts automatically on Monday at 00:00 IST.',
  'already-confirmed':
    'Your score is already confirmed for this week. It is locked until the next reset.',
  'not-eligible': 'This feature is only available to the current Top 10.',
  'showcase-locked': 'Your showcase is locked for the rest of this week.',
  'analysis-failed':
    'We could not read one of the photos clearly. Try again with brighter, sharper pictures.',
  'invalid-image': 'That file is not a supported image. Use a JPG, PNG or WebP file.',
  'image-too-large': 'That image is too large. Choose a smaller file.',
  'rate-limited': 'You have reached the limit for this action. Please try again later.',
  'duplicate-report': 'You have already reported this profile this week.',
  network: 'The network request failed. Check your connection and try again.',
  quota: 'The free usage limit for this service was reached. Please try again later.',
  unknown: 'Something went wrong. Please try again.',
}

export class AppError extends Error {
  readonly code: AppErrorCode
  readonly userMessage: string
  readonly retryable: boolean
  /** Safe, non-sensitive context for logs (never rendered raw to users). */
  readonly context?: Record<string, string | number | boolean>

  constructor(
    code: AppErrorCode,
    options: {
      message?: string
      userMessage?: string
      retryable?: boolean
      context?: Record<string, string | number | boolean>
    } = {},
  ) {
    super(options.message ?? code)
    this.name = 'AppError'
    this.code = code
    this.userMessage = options.userMessage ?? FRIENDLY[code]
    this.retryable = options.retryable ?? false
    this.context = options.context
  }
}

export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError
}

export function toAppError(error: unknown): AppError {
  if (isAppError(error)) return error
  if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
    return new AppError('network')
  }
  return new AppError('unknown', {
    message: error instanceof Error ? error.message : String(error),
  })
}

export function getErrorMessage(error: unknown): string {
  return toAppError(error).userMessage
}

export const backendUnconfigured = (): AppError =>
  new AppError('backend-unconfigured', { retryable: true })

export const notImplemented = (feature = 'This action'): AppError =>
  new AppError('not-implemented', {
    message: `${feature} is not implemented in Phase 1.`,
  })
