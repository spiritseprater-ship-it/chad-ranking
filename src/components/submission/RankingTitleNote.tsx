import { TITLE_DESCRIPTIONS } from '@/config/constants'
import type { RankTitle } from '@/types/domain'

const ORDER: RankTitle[] = ['TRUE ADAM', 'ELITE CHAD', 'TOP 10', 'RANKED', 'UNRANKED']

export function RankingTitleNote() {
  return (
    <div className="rounded-card border border-line bg-canvas/60 p-5">
      <p className="eyebrow">Rank titles</p>
      <ul className="mt-3 space-y-2">
        {ORDER.map((title) => (
          <li key={title} className="flex items-baseline justify-between gap-3">
            <span className="font-display text-[10px] font-semibold uppercase tracking-[0.1em] text-ink">
              {title}
            </span>
            <span className="text-right text-[10px] leading-snug text-muted">
              {TITLE_DESCRIPTIONS[title]}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-line pt-3 text-[10px] leading-relaxed text-muted">
        Titles are fictional competition labels. They are not verified identity
        claims.
      </p>
    </div>
  )
}
