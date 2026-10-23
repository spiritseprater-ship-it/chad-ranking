import { cn } from '@/utils/cn'

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

const SIZES: Record<AvatarSize, string> = {
  xs: 'h-7 w-7 text-[10px]',
  sm: 'h-9 w-9 text-xs',
  md: 'h-11 w-11 text-sm',
  lg: 'h-16 w-16 text-lg',
  xl: 'h-28 w-28 text-3xl sm:h-36 sm:w-36',
}

const TINTS = [
  'bg-forest-tint text-forest',
  'bg-gold-tint text-gold-deep',
  'bg-[#EDEFF3] text-[#4A5566]',
  'bg-[#F1EDE8] text-[#6B5443]',
  'bg-[#EAF0EC] text-[#3E6350]',
]

function initials(username: string): string {
  const clean = username.replace(/[^a-zA-Z0-9]/g, '')
  if (clean.length === 0) return '?'
  return clean.slice(0, 2).toUpperCase()
}

function tintFor(username: string): string {
  let hash = 0
  for (let i = 0; i < username.length; i += 1) {
    hash = (hash * 31 + username.charCodeAt(i)) % 997
  }
  return TINTS[hash % TINTS.length] ?? TINTS[0]!
}

/**
 * Profile images are not uploaded in Phase 1, so most accounts show a
 * designed monogram placeholder. Alt text never exposes private data.
 */
export function ProfileAvatar({
  username,
  imagePath,
  size = 'md',
  ring,
  className,
}: {
  username: string
  imagePath?: string | null
  size?: AvatarSize
  ring?: 'gold' | 'forest' | 'none'
  className?: string
}) {
  const ringClass =
    ring === 'gold'
      ? 'ring-2 ring-gold/70 ring-offset-2 ring-offset-surface'
      : ring === 'forest'
        ? 'ring-2 ring-forest/30 ring-offset-2 ring-offset-surface'
        : ''

  if (imagePath) {
    return (
      <img
        src={imagePath}
        alt={`${username}'s profile picture`}
        className={cn('shrink-0 rounded-full object-cover', SIZES[size], ringClass, className)}
        loading="lazy"
        decoding="async"
        referrerPolicy="no-referrer"
      />
    )
  }

  return (
    <span
      role="img"
      aria-label={`${username}'s profile picture placeholder`}
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center rounded-full border border-black/[0.04] font-display font-semibold tracking-wide',
        SIZES[size],
        tintFor(username),
        ringClass,
        className,
      )}
    >
      {initials(username)}
    </span>
  )
}
