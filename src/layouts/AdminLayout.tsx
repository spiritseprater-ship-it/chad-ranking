import { NavLink, Outlet } from 'react-router-dom'
import {
  ArrowLeft,
  LayoutDashboard,
  ScrollText,
  ShieldCheck,
  Users,
  Gavel,
} from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { AccessDenied, RequireAuth } from '@/components/auth/Guards'
import { useAuth } from '@/hooks/useAuth'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { BackendBanner } from '@/components/common/BackendBanner'
import { cn } from '@/utils/cn'
import { Link } from 'react-router-dom'

const ADMIN_LINKS = [
  { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/admin/users', label: 'Users & scores', icon: Users, end: false },
  { to: '/admin/moderation', label: 'Moderation', icon: Gavel, end: false },
  { to: '/admin/audit', label: 'Audit log', icon: ScrollText, end: false },
]

function AdminFrame() {
  const { user, isAdmin } = useAuth()
  if (!isAdmin) return <AccessDenied />

  return (
    <>
      <PageHeader
        eyebrow="Internal · Authorized staff"
        title="Administration"
        description="Moderate profiles, correct confirmed scores and review reports. Every action is recorded in a minimal audit trail and re-checked by the backend."
        actions={
          <>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-forest/20 bg-forest-tint px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-forest">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
              Administrator
            </span>
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 rounded-field border border-line bg-surface px-3.5 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:text-ink"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              Back to site
            </Link>
          </>
        }
      />

      <div className="container-page py-8 lg:py-10">
        <BackendBanner className="mb-6" />
        <div className="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)]">
          <aside>
            <nav
              aria-label="Administration"
              className="flex gap-1 overflow-x-auto pb-1 lg:sticky lg:top-24 lg:flex-col lg:overflow-visible"
            >
              {ADMIN_LINKS.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        'flex shrink-0 items-center gap-2.5 rounded-field px-3 py-2.5 text-xs font-semibold uppercase tracking-[0.08em] transition-colors',
                        isActive
                          ? 'bg-forest text-white'
                          : 'text-muted hover:bg-subtle hover:text-ink',
                      )
                    }
                  >
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                    {item.label}
                  </NavLink>
                )
              })}
            </nav>

            {user ? (
              <div className="mt-6 hidden items-center gap-2.5 border-t border-line pt-5 lg:flex">
                <ProfileAvatar
                  username={user.username}
                  imagePath={user.profileImagePath}
                  size="sm"
                  ring="forest"
                />
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-ink">
                    {user.username}
                  </p>
                  <p className="text-[10px] uppercase tracking-wider text-muted">
                    Admin session
                  </p>
                </div>
              </div>
            ) : null}
          </aside>

          <div className="min-w-0">
            <Outlet />
          </div>
        </div>
      </div>
    </>
  )
}

export function AdminLayout() {
  return (
    <RequireAuth>
      <AdminFrame />
    </RequireAuth>
  )
}
