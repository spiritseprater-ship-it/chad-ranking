/**
 * Shared domain types.
 *
 * These describe the shape of data the UI consumes. In Phase 2 the Firebase
 * services will map Firestore documents into exactly these types, so pages and
 * components never depend on backend-specific structures.
 */

export type Role = 'member' | 'admin'
export type AccountStatus = 'active' | 'suspended'
export type SubmissionStatus = 'none' | 'provisional' | 'confirmed'
export type ModerationStatus = 'clear' | 'under_review' | 'disqualified'
export type CompetitionStatus = 'active' | 'closed'
export type ShowcaseStatus = 'none' | 'submitted' | 'locked' | 'removed'

export type RankTitle = 'TRUE ADAM' | 'ELITE CHAD' | 'TOP 10' | 'RANKED' | 'UNRANKED'

export const RANKED_POSITIONS = 100
export const SHOWCASE_POSITIONS = 10
export const IST_TIMEZONE = 'Asia/Kolkata'

/** A weekly competition period, defined on the server in Phase 2. */
export interface Competition {
  id: string
  /** Human label, e.g. "19 – 25 OCT 2026". */
  weekLabel: string
  /** ISO-8601 UTC timestamps. */
  startsAt: string
  endsAt: string
  status: CompetitionStatus
  timezone: typeof IST_TIMEZONE
}

/** Signed-in account details safe to render in the UI. */
export interface CurrentUser {
  uid: string
  username: string
  profileImagePath: string | null
  role: Role
  accountStatus: AccountStatus
  createdAt: string
}

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export interface AuthSnapshot {
  status: AuthStatus
  user: CurrentUser | null
}

export interface LeaderboardEntry {
  uid: string
  username: string
  profileImagePath: string | null
  score: number
  submittedAt: string
  rank: number
  title: RankTitle
}

/** Participants beyond the Top 100 are shown by username only. */
export interface DirectoryEntry {
  uid: string
  username: string
  rank: number
}

export interface LeaderboardView {
  competition: Competition
  /** Confirmed, non-disqualified entries for the active competition. */
  ranked: LeaderboardEntry[]
  /** Participants without a confirmed score this week. */
  unconfirmedCount: number
  /** Everyone ranked below position 100 — usernames only. */
  directory: DirectoryEntry[]
  totalParticipants: number
  generatedAt: string
}

export type ScoreCategory = 'pose' | 'expression' | 'creativity' | 'styling'

export interface ScoreBreakdownItem {
  category: ScoreCategory
  label: string
  weight: number
  score: number
  /** Plain-language explanation of the entertainment category. */
  description: string
}

export interface ProvisionalScore {
  total: number
  breakdown: ScoreBreakdownItem[]
  scoringVersion: string
  /** Phase 1 runs only a local, documented browser heuristic. */
  method: 'browser-heuristic'
  analyzedAt: string
}

export interface SubmissionRecord {
  uid: string
  competitionId: string
  confirmedScore: number | null
  status: SubmissionStatus
  submittedAt: string | null
  scoringVersion: string | null
  moderationStatus: ModerationStatus
  locked: boolean
  /** Number of attempts already used this week (server-enforced in Phase 2). */
  attemptsUsed: number
  attemptsAllowed: number
}

export interface WeeklyStatus {
  competition: Competition
  submission: SubmissionRecord | null
  rank: number | null
  title: RankTitle
  canSubmit: boolean
  canRetry: boolean
  /** Human-readable reason when submission is blocked (lock, suspension, etc.). */
  blockedReason: string | null
}

export interface ConfirmSubmissionInput {
  competitionId: string
  score: number
  scoringVersion: string
  analyzedAt: string
}

export interface ConfirmSubmissionResult {
  score: number
  rank: number
  title: RankTitle
  showcaseEligible: boolean
  lockedUntil: string
}

export interface PublicShowcase {
  slogan: string | null
  imagePath: string | null
  rank: number
  title: RankTitle
  submittedAt: string
  locked: boolean
}

export interface PublicProfile {
  uid: string
  username: string
  profileImagePath: string | null
  accountStatus: AccountStatus
  createdAt: string
  competitionId: string
  score: number | null
  rank: number | null
  title: RankTitle | 'NOT YET RANKED'
  showcase: PublicShowcase | null
  isSelf: boolean
}

export interface ShowcaseEligibility {
  competitionId: string
  rank: number | null
  score: number | null
  eligible: boolean
  /** Present when this user already locked a showcase for the current week. */
  showcase: PublicShowcase | null
  reason: string | null
}

export interface ShowcaseSubmissionInput {
  slogan: string
  imageFile: File | null
}

export type ReportCategory =
  | 'impersonation'
  | 'fake-profile'
  | 'inappropriate-image'
  | 'offensive-content'
  | 'spam'

export type ReportStatus = 'pending' | 'actioned' | 'dismissed'

export interface ReportCategoryOption {
  value: ReportCategory
  label: string
  description: string
}

export interface ModerationReport {
  id: string
  reporterUid: string
  reporterUsername: string
  reportedUid: string
  reportedUsername: string
  category: ReportCategory
  categoryLabel: string
  status: ReportStatus
  createdAt: string
}

export type AdminActionType =
  | 'score-correction'
  | 'user-suspended'
  | 'user-restored'
  | 'showcase-removed'
  | 'submission-disqualified'
  | 'profile-picture-removed'
  | 'admin-role-granted'
  | 'admin-role-revoked'
  | 'report-dismissed'
  | 'report-actioned'
  | 'rankings-recalculated'
  | 'competition-reset'

export interface AuditEvent {
  id: string
  actionType: AdminActionType
  actionLabel: string
  actorUid: string
  actorUsername: string
  targetUid: string | null
  targetUsername: string | null
  reason: string
  createdAt: string
}

export interface AdminStats {
  totalUsers: number
  activeParticipants: number
  rankedCount: number
  belowCutoffCount: number
  topTenCount: number
  pendingReports: number
  suspendedCount: number
  competitionId: string
  generatedAt: string
}

export interface AdminUserSummary {
  uid: string
  username: string
  createdAt: string
  accountStatus: AccountStatus
  role: Role
  confirmedScore: number | null
  rank: number | null
  moderationStatus: ModerationStatus
  hasShowcase: boolean
}

export interface AdminOverview {
  stats: AdminStats
  competition: Competition
  topTen: LeaderboardEntry[]
  pendingReports: ModerationReport[]
  recentAudit: AuditEvent[]
}
