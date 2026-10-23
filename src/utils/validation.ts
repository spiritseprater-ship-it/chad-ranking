import {
  PASSWORD_MAX,
  PASSWORD_MIN,
  RESERVED_USERNAMES,
  USERNAME_MAX,
  USERNAME_MIN,
} from '@/config/constants'

const USERNAME_PATTERN = /^[a-zA-Z0-9](?:[a-zA-Z0-9_]*[a-zA-Z0-9])?$/

export interface ValidationResult {
  valid: boolean
  message?: string
}

export function normalizeUsername(username: string): string {
  return username.trim().toLowerCase()
}

/**
 * Client-side username policy. Availability and reservation are enforced by a
 * trusted backend operation in Phase 2; this check only improves UX.
 */
export function validateUsername(rawUsername: string): ValidationResult {
  const username = rawUsername.trim()
  if (!username) return { valid: false, message: 'Choose a username.' }
  if (username.length < USERNAME_MIN) {
    return { valid: false, message: `Use at least ${USERNAME_MIN} characters.` }
  }
  if (username.length > USERNAME_MAX) {
    return { valid: false, message: `Use ${USERNAME_MAX} characters or fewer.` }
  }
  if (!USERNAME_PATTERN.test(username)) {
    return {
      valid: false,
      message: 'Use letters, numbers and underscores. Start and end with a letter or number.',
    }
  }
  if (RESERVED_USERNAMES.has(normalizeUsername(username))) {
    return { valid: false, message: 'That username is reserved.' }
  }
  if (/^[0-9]+$/.test(username)) {
    return { valid: false, message: 'Include at least one letter.' }
  }
  return { valid: true }
}

export function validatePassword(password: string): ValidationResult {
  if (!password) return { valid: false, message: 'Choose a password.' }
  if (password.length < PASSWORD_MIN) {
    return { valid: false, message: `Use at least ${PASSWORD_MIN} characters.` }
  }
  if (password.length > PASSWORD_MAX) {
    return { valid: false, message: `Use ${PASSWORD_MAX} characters or fewer.` }
  }
  if (!/[A-Za-z]/.test(password)) {
    return { valid: false, message: 'Include at least one letter.' }
  }
  if (!/[0-9]/.test(password)) {
    return { valid: false, message: 'Include at least one number.' }
  }
  return { valid: true }
}

export function validatePasswordConfirmation(
  password: string,
  confirmation: string,
): ValidationResult {
  if (!confirmation) return { valid: false, message: 'Re-enter your password.' }
  if (password !== confirmation) {
    return { valid: false, message: 'Passwords do not match.' }
  }
  return { valid: true }
}

export function validateEmail(email: string): ValidationResult {
  const trimmed = email.trim()
  if (!trimmed) return { valid: false, message: 'Enter an email address.' }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(trimmed)) {
    return { valid: false, message: 'Enter a valid email address.' }
  }
  return { valid: true }
}

export function getPasswordStrength(password: string): {
  score: 0 | 1 | 2 | 3
  label: string
} {
  let score = 0
  if (password.length >= PASSWORD_MIN) score += 1
  if (password.length >= 12) score += 1
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1
  if (/[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)) score += 1
  const capped = Math.min(3, score) as 0 | 1 | 2 | 3
  const labels = ['Too short', 'Weak', 'Good', 'Strong'] as const
  return { score: capped, label: labels[capped] }
}
