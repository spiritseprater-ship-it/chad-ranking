import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, X } from 'lucide-react'
import {
  PASSWORD_MIN,
  SLOGAN_MAX_LENGTH,
  USERNAME_MAX,
  USERNAME_MIN,
} from '@/config/constants'
import { backendMode } from '@/services'
import { useAuth } from '@/hooks/useAuth'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useToast } from '@/hooks/useToast'
import { isAppError, getErrorMessage } from '@/services/errors'
import { services } from '@/services'
import {
  getPasswordStrength,
  validateEmail,
  validatePassword,
  validatePasswordConfirmation,
  validateUsername,
} from '@/utils/validation'
import { AuthShell } from '@/components/auth/AuthShell'
import { Button } from '@/components/ui/Button'
import { Checkbox, Field, PasswordInput, PasswordStrength, TextInput } from '@/components/ui/Form'
import { Notice } from '@/components/ui/Notice'
import { BackendBanner } from '@/components/common/BackendBanner'

type Availability = 'idle' | 'checking' | 'available' | 'taken' | 'unknown'
type FieldName = 'username' | 'email' | 'password' | 'confirm' | 'consent'

const BENEFITS = [
  'A permanent public profile and username.',
  'One confirmed weekly score — retake photos before you post.',
  'Top 10 access to the exclusive showcase.',
]

export function SignUpPage() {
  useDocumentTitle('Join the competition')
  const navigate = useNavigate()
  const { user, status, signUp } = useAuth()
  const { toast } = useToast()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [consent, setConsent] = useState(false)
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [availability, setAvailability] = useState<Availability>('idle')

  const debouncedUsername = useDebouncedValue(username, 450)

  useEffect(() => {
    if (status === 'authenticated' && user) {
      navigate('/dashboard', { replace: true })
    }
  }, [status, user, navigate])

  useEffect(() => {
    let active = true
    const formatCheck = validateUsername(debouncedUsername)
    if (!formatCheck.valid || backendMode !== 'demo') {
      setAvailability('idle')
      return
    }
    setAvailability('checking')
    services.auth
      .isUsernameAvailable(debouncedUsername)
      .then((available) => {
        if (active) setAvailability(available ? 'available' : 'taken')
      })
      .catch(() => {
        if (active) setAvailability('unknown')
      })
    return () => {
      active = false
    }
  }, [debouncedUsername])

  const validateAll = (): boolean => {
    const next: Partial<Record<FieldName, string>> = {}
    const usernameCheck = validateUsername(username)
    if (!usernameCheck.valid) next.username = usernameCheck.message
    const emailCheck = validateEmail(email)
    if (!emailCheck.valid) next.email = emailCheck.message
    const passwordCheck = validatePassword(password)
    if (!passwordCheck.valid) next.password = passwordCheck.message
    const confirmCheck = validatePasswordConfirmation(password, confirm)
    if (!confirmCheck.valid) next.confirm = confirmCheck.message
    if (!consent) next.consent = 'Please accept the rules to continue.'
    if (availability === 'taken') next.username = 'That username is already taken.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setFormError(null)
    if (!validateAll()) return
    setSubmitting(true)
    try {
      await signUp({ username: username.trim(), email: email.trim(), password })
      toast({
        variant: 'success',
        title: 'Account created',
        description:
          backendMode === 'demo'
            ? 'Demo session started. Everything here is stored in this browser tab only.'
            : 'Your account is ready. Complete three photos to enter this week.',
      })
      navigate('/dashboard', { replace: true })
    } catch (cause) {
      if (isAppError(cause)) {
        if (cause.code === 'username-taken') {
          setErrors((current) => ({ ...current, username: cause.userMessage }))
        } else if (cause.code === 'email-in-use') {
          setErrors((current) => ({ ...current, email: cause.userMessage }))
        } else if (cause.code === 'weak-password') {
          setErrors((current) => ({ ...current, password: cause.userMessage }))
        } else {
          setFormError(cause.userMessage)
        }
      } else {
        setFormError(getErrorMessage(cause))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const strength = getPasswordStrength(password)

  return (
    <AuthShell
      eyebrow="Create an account"
      title="Claim your place."
      description="One username, one public profile, one weekly rank. Your legal name is never required."
      aside={
        <>
          <p className="eyebrow">What you get</p>
          <ul className="mt-4 space-y-3">
            {BENEFITS.map((benefit) => (
              <li key={benefit} className="flex gap-2.5 text-xs leading-relaxed text-muted">
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-forest" aria-hidden="true" />
                {benefit}
              </li>
            ))}
          </ul>
          <div className="my-5 h-px bg-line" />
          <p className="text-[11px] leading-relaxed text-muted">
            No payment, no follow-for-follow, no voting. Scores are entertainment
            labels, not measurements of appearance or worth.
          </p>
          <p className="mt-4 font-serif text-sm italic text-gold-deep">
            Enter. Compete. Claim your rank.
          </p>
        </>
      }
      footer={
        <>
          Already competing?{' '}
          <Link to="/login" className="font-medium text-forest underline underline-offset-2">
            Log in
          </Link>
        </>
      }
    >
      {backendMode === 'unconfigured' ? (
        <BackendBanner className="mb-6" />
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <Field
          id="signup-username"
          label="Username"
          required
          error={errors.username}
          hint={
            availability === 'checking'
              ? 'Checking availability…'
              : availability === 'available'
                ? 'Available in this preview.'
                : availability === 'taken'
                  ? undefined
                  : `Use letters, numbers and underscores. ${USERNAME_MIN}–${USERNAME_MAX} characters.`
          }
        >
          <div className="relative">
            <TextInput
              id="signup-username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => {
                setUsername(event.target.value)
                if (errors.username) {
                  setErrors((current) => ({ ...current, username: undefined }))
                }
              }}
              placeholder="e.g. Zaid_07"
              maxLength={USERNAME_MAX + 4}
              invalid={Boolean(errors.username)}
              aria-describedby="signup-username-hint signup-username-error"
              required
            />
            {availability === 'available' ? (
              <Check className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-success" aria-hidden="true" />
            ) : availability === 'taken' ? (
              <X className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-danger" aria-hidden="true" />
            ) : null}
          </div>
        </Field>

        <Notice variant="neutral" className="!border-line !bg-subtle/50">
          <span className="text-[11px] leading-relaxed text-muted">
            Choose a username close to the name your friends recognize you by. Do
            not impersonate another person or public figure. Your legal name is not
            required.
          </span>
        </Notice>

        <Field
          id="signup-email"
          label="Email"
          required
          error={errors.email}
          hint="Used for sign-in and password recovery. Never shown on your public profile or the leaderboard."
        >
          <TextInput
            id="signup-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            invalid={Boolean(errors.email)}
            aria-describedby="signup-email-hint signup-email-error"
            required
          />
        </Field>

        <Field
          id="signup-password"
          label="Password"
          required
          error={errors.password}
          hint={`At least ${PASSWORD_MIN} characters, including a number.`}
        >
          <PasswordInput
            id="signup-password"
            name="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            invalid={Boolean(errors.password)}
            aria-describedby="signup-password-hint signup-password-error"
            required
          />
          {password ? (
            <PasswordStrength score={strength.score} label={strength.label} />
          ) : null}
        </Field>

        <Field id="signup-confirm" label="Confirm password" required error={errors.confirm}>
          <PasswordInput
            id="signup-confirm"
            name="confirm-password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            invalid={Boolean(errors.confirm)}
            required
          />
        </Field>

        <Checkbox
          id="signup-consent"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
          error={errors.consent}
          label={
            <>
              I agree to the{' '}
              <Link to="/rules" className="font-medium text-forest underline underline-offset-2">
                rules and privacy policy
              </Link>{' '}
              and understand that CHAD SCORE is an entertainment score. Slogans are
              limited to {SLOGAN_MAX_LENGTH} characters.
            </>
          }
        />

        {formError ? (
          <Notice variant="danger" title="Account not created">
            {formError}
          </Notice>
        ) : null}

        <Button
          type="submit"
          fullWidth
          size="lg"
          loading={submitting}
          disabled={backendMode === 'unconfigured'}
          icon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
          className="flex-row-reverse"
        >
          Create account
        </Button>

        {backendMode === 'unconfigured' ? (
          <p className="text-center text-[11px] leading-relaxed text-muted">
            Registration is disabled until Firebase is configured. See the README
            for the setup checklist.
          </p>
        ) : backendMode === 'demo' ? (
          <p className="text-center text-[11px] leading-relaxed text-muted">
            Preview mode: this account lives in browser memory and is not a real
            registration.
          </p>
        ) : null}
      </form>
    </AuthShell>
  )
}
