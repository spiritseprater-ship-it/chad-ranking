import { useState } from 'react'
import { Search, SlidersHorizontal, Users } from 'lucide-react'
import type { AdminUserSummary } from '@/types/domain'
import { services } from '@/services'
import { useAsync } from '@/hooks/useAsync'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { TextInput } from '@/components/ui/Form'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState, ErrorState, TableSkeleton } from '@/components/ui/States'
import { UserManageDialog } from '@/components/admin/UserManageDialog'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { formatIstDate } from '@/utils/datetime'

export function AdminUsersPage() {
  useDocumentTitle('Admin · Users')
  const [query, setQuery] = useState('')
  const debounced = useDebouncedValue(query, 300)
  const users = useAsync(() => services.admin.listUsers(debounced), [debounced])
  const [selected, setSelected] = useState<AdminUserSummary | null>(null)

  const rows = users.data ?? []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Users & scores</p>
          <h2 className="mt-1.5 font-display text-xl font-semibold text-ink">
            Account management
          </h2>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted">
            Search a public username, review the confirmed entry, and apply an audited
            action. Ranks are recalculated from scores — never set directly.
          </p>
        </div>
        <div className="relative w-full sm:w-64">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <TextInput
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search username"
            aria-label="Search users by username"
            className="h-10 pl-9 text-xs"
          />
        </div>
      </div>

      {users.error ? (
        <ErrorState
          title="User list unavailable"
          message={users.error.userMessage}
          code={users.error.code}
          onRetry={users.reload}
        />
      ) : users.loading && rows.length === 0 ? (
        <TableSkeleton rows={8} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Users}
          title={debounced ? 'No username matches that search.' : 'No accounts yet.'}
          description={
            debounced
              ? 'Search is case-insensitive and matches the public username only.'
              : 'Registered accounts appear here once Firebase authentication is connected.'
          }
          action={
            debounced ? (
              <Button variant="secondary" size="sm" onClick={() => setQuery('')}>
                Clear search
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="overflow-hidden rounded-card border border-line bg-surface">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
              {rows.length} account{rows.length === 1 ? '' : 's'}
              {debounced ? ` matching “${debounced}”` : ''}
            </p>
            <span className="inline-flex items-center gap-1.5 text-[10px] text-muted">
              <SlidersHorizontal className="h-3 w-3" aria-hidden="true" />
              Actions are audited
            </span>
          </div>

          <div className="divide-y divide-line md:hidden">
            {rows.map((user) => (
              <div key={user.uid} className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <ProfileAvatar username={user.username} size="sm" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">@{user.username}</p>
                      <p className="text-[10px] text-muted">Joined {formatIstDate(user.createdAt)}</p>
                    </div>
                  </div>
                  <Badge variant={user.accountStatus === 'active' ? 'success' : 'danger'}>
                    {user.accountStatus}
                  </Badge>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[10px] text-muted">
                  <span>Rank <strong className="text-ink">{user.rank ?? '—'}</strong></span>
                  <span>Score <strong className="text-ink">{user.confirmedScore ?? '—'}</strong></span>
                  <span>Role <strong className="capitalize text-ink">{user.role}</strong></span>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  fullWidth
                  className="mt-3"
                  onClick={() => setSelected(user)}
                >
                  Manage account
                </Button>
              </div>
            ))}
          </div>

          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line">
                  {['Participant', 'Status', 'Rank', 'Score', 'Moderation', 'Joined', ''].map(
                    (heading, index) => (
                      <th
                        key={`${heading}-${index}`}
                        scope="col"
                        className="px-4 py-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted"
                      >
                        {heading}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((user) => (
                  <tr key={user.uid}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <ProfileAvatar username={user.username} size="xs" />
                        <div>
                          <p className="text-xs font-medium text-ink">@{user.username}</p>
                          <p className="text-[10px] capitalize text-muted">
                            {user.role}
                            {user.hasShowcase ? ' · showcase' : ''}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={user.accountStatus === 'active' ? 'success' : 'danger'}>
                        {user.accountStatus}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs tabular-nums text-ink">
                      {user.rank !== null ? `#${user.rank}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs font-semibold tabular-nums text-ink">
                      {user.confirmedScore ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={user.moderationStatus === 'disqualified' ? 'danger' : 'neutral'}
                      >
                        {user.moderationStatus}
                      </Badge>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-[11px] text-muted">
                      {formatIstDate(user.createdAt)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        className="!h-7 !px-2.5 !text-[9px]"
                        onClick={() => setSelected(user)}
                      >
                        Manage
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-[10px] leading-relaxed text-muted">
        Public profiles never display account status notes, emails or moderator-only
        metadata. Actions taken here are stored in the minimal audit log with the
        reason you provide.
      </p>

      <UserManageDialog
        open={selected !== null}
        summary={selected}
        onClose={() => setSelected(null)}
        onChanged={users.reload}
      />
    </div>
  )
}
