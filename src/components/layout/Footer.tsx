import { Link } from 'react-router-dom'
import { APP_NAME, ENTERTAINMENT_DISCLAIMER } from '@/config/constants'
import { useAuth } from '@/hooks/useAuth'
import { Wordmark } from './Logo'

const COMPETE = [
  { label: 'Weekly leaderboard', to: '/leaderboard' },
  { label: 'Participants', to: '/participants' },
  { label: 'Join the competition', to: '/signup' },
]

const INFORMATION = [
  { label: 'How it works', to: '/#how-it-works' },
  { label: 'Rules & privacy', to: '/rules' },
  { label: 'Data status', to: '/rules#data-status' },
]

export function Footer() {
  const { user } = useAuth()
  const accountLinks = user
    ? [
        { label: 'Dashboard', to: '/dashboard' },
        { label: 'My profile', to: `/profile/${encodeURIComponent(user.username)}` },
        ...(user.role === 'admin' ? [{ label: 'Administration', to: '/admin' }] : []),
      ]
    : [
        { label: 'Log in', to: '/login' },
        { label: 'Create an account', to: '/signup' },
      ]

  return (
    <footer className="border-t border-line bg-surface">
      <div className="container-page py-12 sm:py-14">
        <div className="grid gap-10 md:grid-cols-[1.6fr_1fr_1fr_1fr]">
          <div className="max-w-xs">
            <Wordmark />
            <p className="mt-5 text-sm leading-relaxed text-muted">
              A weekly community competition built for friends. Enter, compete,
              and claim your rank.
            </p>
          </div>

          <FooterColumn title="Compete" links={COMPETE} />
          <FooterColumn title="Information" links={INFORMATION} />
          <FooterColumn title="Account" links={accountLinks} />
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-line pt-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xl">
            <p className="text-[11px] leading-relaxed text-muted">
              © {new Date().getFullYear()} {APP_NAME}. {ENTERTAINMENT_DISCLAIMER}
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              Scores are subjective entertainment labels, not measurements of
              appearance, health or worth. Participants may report content for
              human review.
            </p>
          </div>
          <p className="shrink-0 font-serif text-sm italic text-muted">
            {user ? 'The ranking is yours to claim.' : 'Enter. Compete. Claim your rank.'}
          </p>
        </div>
      </div>
    </footer>
  )
}

function FooterColumn({
  title,
  links,
}: {
  title: string
  links: Array<{ label: string; to: string }>
}) {
  return (
    <div>
      <h2 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ink">
        {title}
      </h2>
      <ul className="mt-4 space-y-2.5">
        {links.map((link) => (
          <li key={link.to + link.label}>
            <Link
              to={link.to}
              className="text-[0.8125rem] text-muted transition-colors hover:text-forest"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
