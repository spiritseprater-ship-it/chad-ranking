import { FlaskConical } from 'lucide-react'
import { demoStore } from '@/services/demo/demoStore'
import { Button } from '@/components/ui/Button'

/**
 * Visible ONLY in demo mode. These are sample identities, not real users, and
 * the password is intentionally public.
 */
export function DemoAccountsPanel({
  onSelect,
  busyUsername,
}: {
  onSelect: (username: string) => void
  busyUsername: string | null
}) {
  const accounts = demoStore.getDemoAccounts()
  return (
    <div>
      <div className="flex items-center gap-2">
        <FlaskConical className="h-3.5 w-3.5 text-gold-deep" aria-hidden="true" />
        <p className="eyebrow !text-gold-deep">Sample accounts</p>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">
        Explore each role without registering. Password:{' '}
        <code className="rounded bg-subtle px-1.5 py-0.5 font-mono text-[10px] text-ink">
          {demoStore.demoPassword}
        </code>
      </p>
      <div className="mt-4 space-y-2">
        {accounts.map((account) => (
          <div
            key={account.username}
            className="flex items-center justify-between gap-3 rounded-lg border border-line bg-canvas/60 px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-ink">
                @{account.username}
              </p>
              <p className="mt-0.5 text-[10px] leading-snug text-muted">{account.note}</p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              className="shrink-0 !px-2.5 !text-[9px]"
              loading={busyUsername === account.username}
              onClick={() => onSelect(account.username)}
            >
              Use
            </Button>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[10px] leading-relaxed text-muted">
        Demo state resets when this tab reloads. No credentials are sent anywhere.
      </p>
    </div>
  )
}
