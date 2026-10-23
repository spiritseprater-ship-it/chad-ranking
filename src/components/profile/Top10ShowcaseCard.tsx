import { Lock, Quote } from 'lucide-react'
import type { PublicShowcase, RankTitle } from '@/types/domain'
import { ProfileAvatar } from '@/components/ui/Avatar'
import { RankTitleBadge } from '@/components/common/RankTitleBadge'
import { cn } from '@/utils/cn'

export function ShowcaseImagePlaceholder({
  username,
  className,
}: {
  username: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden bg-forest-900 paper-texture',
        className,
      )}
      role="img"
      aria-label={`Showcase photograph placeholder for ${username}`}
    >
      <div className="absolute inset-5 border border-canvas/10" aria-hidden="true" />
      <span className="font-serif text-[7rem] leading-none text-canvas/[0.13] sm:text-[9rem]" aria-hidden="true">
        {username.slice(0, 1).toUpperCase()}
      </span>
      <div className="absolute inset-x-0 bottom-0 p-5">
        <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-canvas/70">
          Showcase photograph
        </p>
        <p className="mt-1 text-xs text-canvas/70">
          Not added{''}
          <span className="text-canvas/55"> — photo upload arrives with the backend</span>
        </p>
      </div>
    </div>
  )
}

/**
 * Only rendered when the backend says the user is currently Top 10.
 * Never receives or renders a showcase for an ineligible participant.
 */
export function Top10ShowcaseCard({
  username,
  showcase,
  variant = 'full',
  className,
}: {
  username: string
  showcase: PublicShowcase
  variant?: 'full' | 'preview'
  className?: string
}) {
  if (variant === 'preview') {
    return (
      <article className={cn('flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface', className)}>
        <div className="relative flex aspect-[5/4] items-center justify-center overflow-hidden bg-subtle">
          {showcase.imagePath ? (
            <img
              src={showcase.imagePath}
              alt={`${username}'s showcase`}
              className="h-full w-full object-cover"
              loading="lazy"
              decoding="async"
              referrerPolicy="no-referrer"
            />
          ) : (
            <span className="font-serif text-6xl italic text-forest/20" aria-hidden="true">
              {username.slice(0, 1).toUpperCase()}
            </span>
          )}
          <span className="absolute left-3 top-3">
            <RankTitleBadge title={showcase.title as RankTitle} />
          </span>
        </div>
        <div className="flex flex-1 flex-col p-4">
          <div className="flex items-baseline justify-between gap-3">
            <p className="truncate font-display text-base font-semibold text-ink">{username}</p>
            <p className="shrink-0 text-[10px] font-medium uppercase tracking-wider text-muted">
              Rank {showcase.rank}
            </p>
          </div>
          {showcase.slogan ? (
            <p className="mt-2 line-clamp-2 font-serif text-[0.9375rem] italic leading-snug text-muted">
              “{showcase.slogan}”
            </p>
          ) : (
            <p className="mt-2 text-xs text-muted">No slogan submitted.</p>
          )}
        </div>
      </article>
    )
  }

  return (
    <article className={cn('overflow-hidden rounded-card border border-line bg-surface', className)}>
      <div className="relative overflow-hidden bg-forest-900">
        {showcase.imagePath ? (
          <img
            src={showcase.imagePath}
            alt={`${username}'s showcase photograph`}
            className="aspect-[4/3] w-full object-cover sm:aspect-[16/10]"
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
          />
        ) : (
          <ShowcaseImagePlaceholder username={username} />
        )}
        <div className="absolute left-4 top-4 flex items-center gap-2">
          <RankTitleBadge title={showcase.title as RankTitle} />
        </div>
      </div>
      <div className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <ProfileAvatar username={username} size="sm" ring="gold" />
            <div>
              <p className="font-display text-base font-semibold text-ink">{username}</p>
              <p className="text-[10px] uppercase tracking-[0.14em] text-muted">
                Rank #{showcase.rank} · {showcase.rank <= 10 ? 'Top 10 showcase' : ''}
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">
            <Lock className="h-3 w-3" aria-hidden="true" />
            Locked this week
          </span>
        </div>
        {showcase.slogan ? (
          <blockquote className="mt-5 border-l border-gold/50 pl-4">
            <Quote className="mb-1 h-3.5 w-3.5 text-gold" aria-hidden="true" />
            <p className="font-serif text-lg italic leading-relaxed text-ink sm:text-xl">
              {showcase.slogan}
            </p>
          </blockquote>
        ) : (
          <p className="mt-5 text-sm text-muted">This participant did not add a slogan.</p>
        )}
      </div>
    </article>
  )
}
