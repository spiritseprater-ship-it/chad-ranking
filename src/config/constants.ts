import type { RankTitle, ReportCategoryOption } from '@/types/domain'

export const APP_NAME = 'CHAD RANKING'
export const APP_TAGLINE = 'THE RANKING IS YOURS TO CLAIM.'
export const APP_SUBTAGLINE =
  'Enter the weekly competition, discover your score, and compete for a place among the Top 100.'

export const NAV_LINKS = [
  { label: 'Leaderboard', to: '/leaderboard' },
  { label: 'Participants', to: '/participants' },
  { label: 'How it works', to: '/#how-it-works' },
  { label: 'Rules', to: '/rules' },
] as const

export const USERNAME_MIN = 3
export const USERNAME_MAX = 20
export const PASSWORD_MIN = 8
export const PASSWORD_MAX = 72

/** Client-side only; the authoritative check lives behind the backend. */
export const RESERVED_USERNAMES = new Set([
  'admin',
  'administrator',
  'chad',
  'chadranking',
  'chad-ranking',
  'moderator',
  'mod',
  'owner',
  'root',
  'support',
  'staff',
  'official',
  'system',
  'winner',
  'judge',
  'ranking',
  'trueadam',
  'true-adam',
])

export const SCORING_CATEGORIES = [
  {
    category: 'pose',
    label: 'Pose & presentation',
    weight: 0.3,
    description: 'Variety and presence across your three photos.',
  },
  {
    category: 'expression',
    label: 'Expression & confidence',
    weight: 0.25,
    description: 'How clearly and confidently the photo set reads.',
  },
  {
    category: 'creativity',
    label: 'Photo creativity',
    weight: 0.25,
    description: 'Light, colour and detail in the images.',
  },
  {
    category: 'styling',
    label: 'Theme & styling',
    weight: 0.2,
    description: 'Consistency of the look across all three photos.',
  },
] as const

export const REPORT_CATEGORIES: ReportCategoryOption[] = [
  {
    value: 'impersonation',
    label: 'Impersonation',
    description: 'Pretending to be another person or public figure.',
  },
  {
    value: 'fake-profile',
    label: 'Fake profile',
    description: 'The account appears not to belong to a real participant.',
  },
  {
    value: 'inappropriate-image',
    label: 'Inappropriate image',
    description: 'A photo that should not be shown publicly.',
  },
  {
    value: 'offensive-content',
    label: 'Offensive content',
    description: 'A slogan or profile that is abusive or offensive.',
  },
  {
    value: 'spam',
    label: 'Spam',
    description: 'Duplicate or disruptive submissions.',
  },
]

export const PROFILE_PHOTO_LIMIT_MB = 1
export const SHOWCASE_PHOTO_LIMIT_MB = 1.5
export const ANALYSIS_PHOTO_LIMIT_MB = 8
export const SLOGAN_MAX_LENGTH = 120

export function rankTitleFor(rank: number | null): RankTitle {
  if (rank === null) return 'UNRANKED'
  if (rank === 1) return 'TRUE ADAM'
  if (rank <= 3) return 'ELITE CHAD'
  if (rank <= 10) return 'TOP 10'
  if (rank <= 100) return 'RANKED'
  return 'UNRANKED'
}

export const TITLE_DESCRIPTIONS: Record<RankTitle, string> = {
  'TRUE ADAM': 'The highest confirmed score of the week.',
  'ELITE CHAD': 'Second and third place in the weekly ranking.',
  'TOP 10': 'A place in the exclusive weekly showcase.',
  RANKED: 'Inside the official Top 100.',
  UNRANKED: 'Below the Top 100, or not yet ranked.',
}

export const ENTERTAINMENT_DISCLAIMER =
  'CHAD SCORE is a fictional entertainment score for a friendly weekly competition. It is not a measurement of attractiveness, health, or personal worth.'
