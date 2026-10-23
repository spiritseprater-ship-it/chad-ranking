import type {
  AdminOverview,
  AdminUserSummary,
  AuditEvent,
  AuthSnapshot,
  Competition,
  ConfirmSubmissionInput,
  ConfirmSubmissionResult,
  CurrentUser,
  LeaderboardView,
  ModerationReport,
  PublicProfile,
  ReportCategory,
  ShowcaseEligibility,
  ShowcaseSubmissionInput,
  SubmissionRecord,
  WeeklyStatus,
} from './domain'

/**
 * Backend contracts. Phase 1 ships a clearly labelled in-memory demo
 * implementation; Phase 2 will supply Firebase-backed implementations of the
 * exact same interfaces, so no page needs to change.
 */
export interface AuthService {
  getSnapshot(): Promise<AuthSnapshot>
  subscribe(listener: (snapshot: AuthSnapshot) => void): () => void
  signUp(input: { username: string; email: string; password: string }): Promise<CurrentUser>
  /** `identifier` is a username or (once Firebase is connected) an email. */
  signIn(input: { identifier: string; password: string }): Promise<CurrentUser>
  signOut(): Promise<void>
  sendPasswordReset(input: { email: string }): Promise<void>
  isUsernameAvailable(username: string): Promise<boolean>
  /** Kept for demo-only convenience; Firebase builds ignore this. */
  listDemoAccounts?(): string[]
}

export interface ProfileService {
  getPublicProfile(username: string): Promise<PublicProfile>
}

export interface LeaderboardService {
  getActiveCompetition(): Promise<Competition>
  getLeaderboard(): Promise<LeaderboardView>
}

export interface SubmissionService {
  getWeeklyStatus(uid: string): Promise<WeeklyStatus>
  /**
   * Phase 2: this must be a trusted callable/Cloud Function that validates the
   * active competition, recomputes rank server-side and writes the submission.
   */
  confirmSubmission(input: ConfirmSubmissionInput): Promise<ConfirmSubmissionResult>
}

export interface ShowcaseService {
  getEligibility(): Promise<ShowcaseEligibility>
  submitShowcase(input: ShowcaseSubmissionInput): Promise<void>
}

export interface ReportService {
  submitReport(input: {
    reportedUid: string
    category: ReportCategory
  }): Promise<{ status: 'accepted' }>
}

export interface AdminService {
  getOverview(): Promise<AdminOverview>
  listUsers(query?: string): Promise<AdminUserSummary[]>
  suspendUser(input: { uid: string; reason: string }): Promise<void>
  restoreUser(input: { uid: string; reason: string }): Promise<void>
  correctScore(input: { uid: string; score: number; reason: string }): Promise<void>
  removeShowcase(input: { uid: string; reason: string }): Promise<void>
  disqualifySubmission(input: { uid: string; reason: string }): Promise<void>
  restoreSubmission(input: { uid: string; reason: string }): Promise<void>
  removeProfilePicture(input: { uid: string; reason: string }): Promise<void>
  recalculateRankings(): Promise<{ rankedCount: number }>
  getModerationQueue(): Promise<ModerationReport[]>
  resolveReport(input: { reportId: string; action: 'actioned' | 'dismissed' }): Promise<void>
  getAuditEvents(): Promise<AuditEvent[]>
}

/**
 * Permanent media only (profile photo, eligible showcase photo). Raw scoring
 * photos never touch this service — they live in browser memory.
 */
export interface MediaService {
  uploadProfilePhoto(file: File): Promise<{ path: string }>
  uploadShowcasePhoto(file: File): Promise<{ path: string }>
  deleteShowcasePhoto(path: string): Promise<void>
}

/** Placeholder until Phase 2 wires real profile-picture editing. */
export type UploadPreference = 'profile' | 'showcase'

export interface Services {
  mode: BackendMode
  auth: AuthService
  profiles: ProfileService
  leaderboard: LeaderboardService
  submissions: SubmissionService
  showcases: ShowcaseService
  reports: ReportService
  admin: AdminService
  media: MediaService
}

export type BackendMode = 'firebase' | 'demo' | 'unconfigured'

export type { SubmissionRecord }
