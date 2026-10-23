import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { backendMode, services } from '@/services'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { getErrorMessage } from '@/services/errors'
import { validateEmail } from '@/utils/validation'
import { AuthShell } from '@/components/auth/AuthShell'
import { Button } from '@/components/ui/Button'
import { Field, TextInput } from '@/components/ui/Form'
import { Notice } from '@/components/ui/Notice'
import { BackendBanner } from '@/components/common/BackendBanner'

export function ForgotPasswordPage() {
  useDocumentTitle('Password recovery')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | undefined>()
  const [formError, setFormError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const emailCheck = validateEmail(email)
    if (!emailCheck.valid) {
      setError(emailCheck.message)
      return
    }
    setError(undefined)
    setFormError(null)
    setSubmitting(true)
    try {
      await services.auth.sendPasswordReset({ email: email.trim() })
      setSent(true)
    } catch (cause) {
      setFormError(getErrorMessage(cause))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Reset your password."
      description="Password recovery is handled by Firebase Authentication. Enter the email attached to your account and Firebase will send a secure reset link."
      footer={
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-forest underline underline-offset-2"
        >
          <ArrowLeft className="h-3 w-3" aria-hidden="true" />
          Back to log in
        </Link>
      }
    >
      {backendMode === 'unconfigured' ? <BackendBanner className="mb-6" /> : null}

      {sent ? (
        <Notice variant="success" title="Check your inbox">
          If an account exists for that address, Firebase will send a reset link.
          For privacy, this screen does not confirm whether an account exists.
        </Notice>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <Field
            id="recovery-email"
            label="Email"
            required
            error={error}
            hint="The recovery email you registered with, never shown publicly."
          >
            <TextInput
              id="recovery-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              invalid={Boolean(error)}
              required
            />
          </Field>

          {formError ? (
            <Notice variant="warning" title="Recovery unavailable">
              {formError}
            </Notice>
          ) : null}

          <Button
            type="submit"
            fullWidth
            loading={submitting}
            disabled={backendMode === 'unconfigured'}
          >
            Send reset link
          </Button>

          {backendMode === 'demo' ? (
            <p className="text-[11px] leading-relaxed text-muted">
              Preview mode: no email is sent. Firebase Authentication is required
              before password recovery can work, so this action fails safely instead
              of pretending a reset happened.
            </p>
          ) : null}
        </form>
      )}
    </AuthShell>
  )
}
