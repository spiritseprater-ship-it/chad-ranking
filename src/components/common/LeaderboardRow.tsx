import { Link } from 'react-router-dom'
import type { LeaderboardEntry } from '@/types/domain'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { RankTitleBadge } from './RankTitleBadge'
import { cn } from '@/utils/cn'

export function LeaderboardRow({
  entry,
  showAvatar = false,
  isCurrentUser = false,
  emphasise = false,
}: {
  entry: LeaderboardEntry
  showAvatar?: boolean
  isCurrentUser?: boolean
  emphasise?: boolean
}) {
  return (
    <Link
      to={`/profile/${encodeURIComponent(entry.username)}`}
      aria-label={`Rank ${entry.rank}, ${entry.username}, score ${entry.score} out of 100`}
      className={cn(
        'group flex items-center gap-3 rounded-lg px-3 py-3 transition-colors sm:gap-4 sm:px-4',
        'hover:bg-subtle/70 focus-visible:bg-subtle/70',
        isCurrentUser && 'bg-forest-tint/50',
        emphasise && 'bg-surface',
      )}
    >
      <span
        className={cn(
          'w-8 shrink-0 text-right font-display text-sm font-semibold tabular-nums',
          entry.rank === 1 ? 'text-gold-deep' : entry.rank <= 10 ? 'text-forest' : 'text-muted',
        )}
      >
        {entry.rank}
      </span>
      {showAvatar ? (
        <ProfileAvatar
          username={entry.username}
          imagePath={entry.profileImagePath}
          size="sm"
          ring={entry.rank === 1 ? 'gold' : 'none'}
        />
      ) : null}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">
          {entry.username}
          {isCurrentUser ? (
            <span className="ml-2 rounded-full bg-forest px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white">
              You
            </span>
          ) : null}
        </p>
        {entry.rank <= 10 ? (
          <div className="mt-1">
            <RankTitleBadge title={entry.title} className="!px-1.5 !py-0.5 !text-[8px]" />
          </div>
        ) : null}
      </div>
      <div className="shrink-0 text-right">
        <p className="font-display text-sm font-semibold tabular-nums text-ink">
          {entry.score}
          <span className="ml-0.5 text-[10px] font-normal text-muted">/100</span>
        </p>
      </div>
    </Link>
  )
}
