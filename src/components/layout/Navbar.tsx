import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, LogOut, Menu, Shield, UserRound, X } from 'lucide-react'
import { NAV_LINKS } from '@/config/constants'
import { useAuth } from '@/hooks/useAuth'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { Button, ButtonLink } from '@/components/ui/Button'
import { cn } from '@/utils/cn'
import { Logo } from './Logo'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'inline-flex h-8 items-center text-[0.6875rem] font-semibold uppercase tracking-[0.14em] transition-colors',
    isActive ? 'text-ink' : 'text-muted hover:text-ink',
  )

export function Navbar() {
  const { user, status, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname, location.hash])

  useEffect(() => {
    if (!mobileOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [mobileOpen])

  const handleSignOut = async () => {
    await signOut()
    setMobileOpen(false)
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/92 backdrop-blur-md supports-[backdrop-filter]:bg-canvas/80">
      <div className="container-page flex h-16 items-center justify-between gap-4">
        <Logo compact />

        <nav aria-label="Primary" className="hidden items-center gap-7 lg:flex">
          {NAV_LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass} end={false}>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          {status === 'loading' ? (
            <span className="h-9 w-24 animate-pulse rounded-field bg-subtle" aria-hidden="true" />
          ) : user ? (
            <>
              <ButtonLink to="/dashboard" variant="ghost" size="sm" icon={<LayoutDashboard className="h-3.5 w-3.5" aria-hidden="true" />}>
                Dashboard
              </ButtonLink>
              {user.role === 'admin' ? (
                <ButtonLink to="/admin" variant="ghost" size="sm" icon={<Shield className="h-3.5 w-3.5" aria-hidden="true" />}>
                  Admin
                </ButtonLink>
              ) : null}
              <Link
                to={`/profile/${encodeURIComponent(user.username)}`}
                className="ml-1 flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-3 transition hover:border-forest/25"
                aria-label="Your profile"
              >
                <ProfileAvatar username={user.username} imagePath={user.profileImagePath} size="xs" />
                <span className="max-w-[7rem] truncate text-xs font-medium text-ink">
                  {user.username}
                </span>
              </Link>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSignOut}
                icon={<LogOut className="h-3.5 w-3.5" aria-hidden="true" />}
                aria-label="Log out"
              >
                <span className="sr-only xl:not-sr-only">Log out</span>
              </Button>
            </>
          ) : (
            <>
              <ButtonLink to="/login" variant="ghost" size="sm">
                Log in
              </ButtonLink>
              <ButtonLink to="/signup" size="sm">
                Join the competition
              </ButtonLink>
            </>
          )}
        </div>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-field border border-line bg-surface text-ink lg:hidden"
          onClick={() => setMobileOpen((current) => !current)}
          aria-expanded={mobileOpen}
          aria-controls="mobile-navigation"
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        >
          {mobileOpen ? <X className="h-4 w-4" aria-hidden="true" /> : <Menu className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>

      {mobileOpen ? (
        <div id="mobile-navigation" className="border-t border-line bg-canvas lg:hidden">
          <nav aria-label="Mobile" className="container-page flex flex-col gap-1 py-4">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  cn(
                    'flex h-11 items-center rounded-field px-3 text-sm font-medium',
                    isActive ? 'bg-subtle text-ink' : 'text-muted hover:bg-subtle/60 hover:text-ink',
                  )
                }
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </NavLink>
            ))}

            <div className="my-2 h-px bg-line" />

            {status === 'loading' ? (
              <div className="h-11 animate-pulse rounded-field bg-subtle" aria-hidden="true" />
            ) : user ? (
              <>
                <NavLink
                  to="/dashboard"
                  className="flex h-11 items-center gap-2 rounded-field px-3 text-sm font-medium text-muted hover:bg-subtle/60 hover:text-ink"
                  onClick={() => setMobileOpen(false)}
                >
                  <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
                  Dashboard
                </NavLink>
                <NavLink
                  to={`/profile/${encodeURIComponent(user.username)}`}
                  className="flex h-11 items-center gap-2 rounded-field px-3 text-sm font-medium text-muted hover:bg-subtle/60 hover:text-ink"
                  onClick={() => setMobileOpen(false)}
                >
                  <UserRound className="h-4 w-4" aria-hidden="true" />
                  My profile
                </NavLink>
                {user.role === 'admin' ? (
                  <NavLink
                    to="/admin"
                    className="flex h-11 items-center gap-2 rounded-field px-3 text-sm font-medium text-muted hover:bg-subtle/60 hover:text-ink"
                    onClick={() => setMobileOpen(false)}
                  >
                    <Shield className="h-4 w-4" aria-hidden="true" />
                    Admin
                  </NavLink>
                ) : null}
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="flex h-11 items-center gap-2 rounded-field px-3 text-left text-sm font-medium text-muted hover:bg-subtle/60 hover:text-ink"
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  Log out
                </button>
              </>
            ) : (
              <div className="grid grid-cols-2 gap-2 pt-1">
                <ButtonLink to="/login" variant="secondary" fullWidth>
                  Log in
                </ButtonLink>
                <ButtonLink to="/signup" fullWidth>
                  Join
                </ButtonLink>
              </div>
            )}
          </nav>
        </div>
      ) : null}
    </header>
  )
}
