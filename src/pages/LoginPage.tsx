import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, LockKeyhole } from 'lucide-react'
import { backendMode } from '@/services'
import { demoStore } from '@/services/demo/demoStore'
import { useAuth } from '@/hooks/useAuth'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useToast } from '@/hooks/useToast'
import { getErrorMessage, isAppError } from '@/services/errors'
import { AuthShell } from '@/components/auth/AuthShell'
import { DemoAccountsPanel } from '@/components/auth/DemoAccountsPanel'
import { Button } from '@/components/ui/Button'
import { Field, PasswordInput, TextInput } from '@/components/ui/Form'
import { Notice } from '@/components/ui/Notice'
import { BackendBanner } from '@/components/common/BackendBanner'

interface LoginLocationState {
  from?: string
}

export function LoginPage() {
  useDocumentTitle('Log in')
  const navigate = useNavigate()
  const location = useLocation()
  const { user, status, signIn } = useAuth()
  const { toast } = useToast()

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ identifier?: string; password?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [demoBusy, setDemoBusy] = useState<string | null>(null)

  const state = location.state as LoginLocationState | null
  const redirectTo =
    state?.from && state.from.startsWith('/') && !state.from.startsWith('/login')
      ? state.from
      : '/dashboard'

  useEffect(() => {
    if (status === 'authenticated' && user) {
      navigate(redirectTo, { replace: true })
    }
  }, [status, user, navigate, redirectTo])

  const finishLogin = async (identifierValue: string, passwordValue: string) => {
    const nextErrors: typeof errors = {}
    if (!identifierValue.trim()) nextErrors.identifier = 'Enter your username or email.'
    if (!passwordValue) nextErrors.password = 'Enter your password.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setFormError(null)
    setSubmitting(true)
    try {
      const account = await signIn({
        identifier: identifierValue.trim(),
        password: passwordValue,
      })
      toast({
        variant: 'success',
        title: `Welcome back, ${account.username}`,
        description:
          backendMode === 'demo'
            ? 'Demo session started in this tab.'
            : 'Your session is active.',
      })
    } catch (cause) {
      if (isAppError(cause)) {
        setFormError(cause.userMessage)
      } else {
        setFormError(getErrorMessage(cause))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    await finishLogin(identifier, password)
  }

  const handleDemoLogin = async (username: string) => {
    setIdentifier(username)
    setPassword(demoStore.demoPassword)
    setDemoBusy(username)
    try {
      await finishLogin(username, demoStore.demoPassword)
    } finally {
      setDemoBusy(null)
    }
  }

  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Return to the board."
      description="Log in to check your weekly status, confirm a score, or manage the competition."
      aside={
        backendMode === 'demo' ? (
          <DemoAccountsPanel onSelect={handleDemoLogin} busyUsername={demoBusy} />
        ) : (
          <>
            <p className="eyebrow">This week</p>
            <ul className="mt-4 space-y-3 text-xs leading-relaxed text-muted">
              <li className="flex gap-2.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gold" aria-hidden="true" />
                One confirmed score per account.
              </li>
              <li className="flex gap-2.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gold" aria-hidden="true" />
                Top 10 unlocks the showcase.
              </li>
              <li className="flex gap-2.5">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-gold" aria-hidden="true" />
                New competition every Monday, 00:00 IST.
              </li>
            </ul>
            <p className="mt-5 border-t border-line pt-4 text-[11px] leading-relaxed text-muted">
              Sessions are handled by Firebase Authentication once the backend is
              connected. This build never stores real credentials.
            </p>
          </>
        )
      }
      footer={
        <>
          New to the competition?{' '}
          <Link to="/signup" className="font-medium text-forest underline underline-offset-2">
            Create an account
          </Link>
        </>
      }
    >
      {backendMode === 'unconfigured' ? <BackendBanner className="mb-6" /> : null}

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <Field
          id="login-identifier"
          label="Username or email"
          required
          error={errors.identifier}
          hint="Public profiles only ever show your username."
        >
          <TextInput
            id="login-identifier"
            name="identifier"
            autoComplete="username"
            value={identifier}
            onChange={(event) => {
              setIdentifier(event.target.value)
              if (errors.identifier) {
                setErrors((current) => ({ ...current, identifier: undefined }))
              }
            }}
            placeholder="Your username"
            invalid={Boolean(errors.identifier)}
            required
          />
        </Field>

        <Field id="login-password" label="Password" required error={errors.password}>
          <PasswordInput
            id="login-password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
              if (errors.password) {
                setErrors((current) => ({ ...current, password: undefined }))
              }
            }}
            invalid={Boolean(errors.password)}
            required
          />
        </Field>

        <div className="flex items-center justify-between gap-4">
          <Link
            to="/forgot-password"
            className="text-xs font-medium text-forest underline underline-offset-2"
          >
            Forgot your password?
          </Link>
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.1em] text-muted">
            <LockKeyhole className="h-3 w-3" aria-hidden="true" />
            Secure session
          </span>
        </div>

        {formError ? (
          <Notice variant="danger" title="Could not log in">
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
          Log in
        </Button>

        {backendMode === 'demo' ? (
          <p className="rounded-lg border border-gold/25 bg-gold-tint/40 px-3 py-2 text-[11px] leading-relaxed text-gold-deep">
            Preview build: sign-in uses sample accounts in this browser tab only.
            Firebase Authentication is not connected.
          </p>
        ) : backendMode === 'unconfigured' ? (
          <p className="text-center text-[11px] leading-relaxed text-muted">
            Login is disabled until Firebase Authentication is configured.
          </p>
        ) : null}
      </form>
    </AuthShell>
  )
}
