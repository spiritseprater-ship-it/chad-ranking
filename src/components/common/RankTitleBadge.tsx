import { Crown, Shield, Star } from 'lucide-react'
import type { RankTitle } from '@/types/domain'
import { Badge } from '@/components/ui/Badge'

export type DisplayTitle = RankTitle | 'NOT YET RANKED'

export function RankTitleBadge({
  title,
  className,
}: {
  title: DisplayTitle
  className?: string
}) {
  if (title === 'TRUE ADAM') {
    return (
      <Badge variant="gold" className={className} icon={<Crown className="h-3 w-3" aria-hidden="true" />}>
        True Adam
      </Badge>
    )
  }
  if (title === 'ELITE CHAD') {
    return (
      <Badge variant="gold" className={className} icon={<Star className="h-3 w-3" aria-hidden="true" />}>
        Elite Chad
      </Badge>
    )
  }
  if (title === 'TOP 10') {
    return (
      <Badge variant="forest" className={className} icon={<Shield className="h-3 w-3" aria-hidden="true" />}>
        Top 10
      </Badge>
    )
  }
  if (title === 'RANKED') {
    return (
      <Badge variant="neutral" className={className}>
        Ranked
      </Badge>
    )
  }
  if (title === 'NOT YET RANKED') {
    return (
      <Badge variant="outline" className={className}>
        Not yet ranked
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className={className}>
      Unranked
    </Badge>
  )
}
