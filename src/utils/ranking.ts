import { rankTitleFor } from '@/config/constants'
import type { DirectoryEntry, LeaderboardEntry, RankTitle } from '@/types/domain'

export interface RankableSubmission {
  uid: string
  username: string
  profileImagePath: string | null
  score: number
  submittedAt: string
}

/**
 * Documented ordering:
 *   1. confirmed score, descending
 *   2. submission timestamp, ascending (earlier submission wins a tie)
 *   3. user id, ascending (stable deterministic tie-breaker)
 *
 * Ranks are derived from this order; no client-submitted rank values are ever
 * trusted. Shared ranks are intentionally not used.
 */
export function compareSubmissions(
  a: RankableSubmission,
  b: RankableSubmission,
): number {
  if (b.score !== a.score) return b.score - a.score
  const aTime = new Date(a.submittedAt).getTime()
  const bTime = new Date(b.submittedAt).getTime()
  if (aTime !== bTime) return aTime - bTime
  return a.uid.localeCompare(b.uid)
}

export function buildRankedEntries(
  submissions: RankableSubmission[],
  rankedLimit = 100,
): { ranked: LeaderboardEntry[]; directory: DirectoryEntry[] } {
  const sorted = [...submissions].sort(compareSubmissions)
  const ranked: LeaderboardEntry[] = []
  const directory: DirectoryEntry[] = []

  sorted.forEach((submission, index) => {
    const position = index + 1
    if (position <= rankedLimit) {
      ranked.push({
        ...submission,
        rank: position,
        title: rankTitleFor(position),
      })
    } else {
      directory.push({
        uid: submission.uid,
        username: submission.username,
        rank: position,
      })
    }
  })

  return { ranked, directory }
}

export function titleForScore(rank: number | null): RankTitle {
  return rankTitleFor(rank)
}

export function findEntryRank(
  entries: ReadonlyArray<{ uid: string; rank: number }>,
  uid: string,
): number | null {
  return entries.find((entry) => entry.uid === uid)?.rank ?? null
}
