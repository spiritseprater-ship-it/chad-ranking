import { Link } from 'react-router-dom'
import { ArrowUpRight, Crown } from 'lucide-react'
import type { LeaderboardEntry } from '@/types/domain'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { RankTitleBadge } from './RankTitleBadge'
import { cn } from '@/utils/cn'

/**
 * Editorial cards for ranks 1–3. Rank 1 carries the only gold frame.
 */
export function TopRankCard({
  entry,
  size = 'standard',
  className,
}: {
  entry: LeaderboardEntry
  size?: 'standard' | 'feature'
  className?: string
}) {
  const isFirst = entry.rank === 1
  return (
    <Link
      to={`/profile/${encodeURIComponent(entry.username)}`}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-card border bg-surface p-5 transition-colors hover:border-forest/25 sm:p-6',
        isFirst ? 'border-gold/45' : 'border-line',
        className,
      )}
    >
      {isFirst ? (
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold to-transparent" />
      ) : null}
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-center gap-2">
          <span
            className={cn(
              'font-serif italic',
              isFirst ? 'text-gold-deep' : 'text-muted',
              size === 'feature' ? 'text-lg' : 'text-base',
            )}
          >
            No. {entry.rank}
          </span>
          {isFirst ? <Crown className="h-3.5 w-3.5 text-gold" aria-hidden="true" /> : null}
        </span>
        <ArrowUpRight className="h-4 w-4 text-muted/70 transition group-hover:text-forest" aria-hidden="true" />
      </div>

      <div className="mt-5 flex items-center gap-3.5">
        <ProfileAvatar
          username={entry.username}
          imagePath={entry.profileImagePath}
          size={size === 'feature' ? 'lg' : 'md'}
          ring={isFirst ? 'gold' : 'none'}
        />
        <div className="min-w-0">
          <p
            className={cn(
              'truncate font-display font-semibold tracking-tight text-ink',
              size === 'feature' ? 'text-xl sm:text-2xl' : 'text-lg',
            )}
          >
            {entry.username}
          </p>
          <p className="mt-1">
            <RankTitleBadge title={entry.title} />
          </p>
        </div>
      </div>

      <div className="mt-auto flex items-end justify-between gap-4 pt-8">
        <div>
          <p className="text-[0.5625rem] font-semibold uppercase tracking-[0.16em] text-muted">
            Chad score
          </p>
          <p className="mt-1 font-display leading-none">
            <span
              className={cn(
                'font-semibold tabular-nums tracking-tight',
                size === 'feature' ? 'text-4xl' : 'text-3xl',
                isFirst ? 'text-gold-deep' : 'text-ink',
              )}
            >
              {entry.score}
            </span>
            <span className="ml-1 text-xs text-muted">/100</span>
          </p>
        </div>
        <p className="text-right text-[0.625rem] leading-relaxed text-muted">
          Confirmed
          <br />
          weekly entry
        </p>
      </div>
    </Link>
  )
}

/** Compact three-place preview used in the landing hero. */
export function TopThreeList({ entries }: { entries: LeaderboardEntry[] }) {
  return (
    <ol className="divide-y divide-line">
      {entries.map((entry) => (
        <li key={entry.uid}>
          <Link
            to={`/profile/${encodeURIComponent(entry.username)}`}
            className="group flex items-center gap-3 py-3 transition-colors hover:bg-subtle/50"
          >
            <span
              className={cn(
                'w-5 text-center font-serif text-sm italic',
                entry.rank === 1 ? 'text-gold-deep' : 'text-muted',
              )}
            >
              {entry.rank}
            </span>
            <ProfileAvatar
              username={entry.username}
              imagePath={entry.profileImagePath}
              size="sm"
              ring={entry.rank === 1 ? 'gold' : 'none'}
            />
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
              {entry.username}
            </span>
            <span className="shrink-0 font-display text-sm font-semibold tabular-nums text-ink">
              {entry.score}
            </span>
          </Link>
        </li>
      ))}
    </ol>
  )
}
