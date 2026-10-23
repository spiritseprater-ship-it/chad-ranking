import type { AuthSnapshot, AuthStatus, CurrentUser } from '@/types/domain'
import type {
  AdminService,
  AuthService,
  LeaderboardService,
  MediaService,
  ProfileService,
  ReportService,
  Services,
  ShowcaseService,
  SubmissionService,
} from '@/types/services'
import { AppError, notImplemented } from '../errors'
import { demoStore } from './demoStore'

const listeners = new Set<(snapshot: AuthSnapshot) => void>()
let snapshot: AuthSnapshot = { status: 'loading', user: null }
let initialised = false

function toStatus(user: CurrentUser | null): AuthStatus {
  return user ? 'authenticated' : 'anonymous'
}

function initialise(): void {
  if (initialised) return
  initialised = true
  const user = demoStore.getSnapshot().user
  snapshot = { status: toStatus(user), user }
}

function emit(): void {
  listeners.forEach((listener) => listener(snapshot))
}

function setUser(user: CurrentUser | null): void {
  snapshot = { status: toStatus(user), user }
  emit()
}

const auth: AuthService = {
  async getSnapshot() {
    initialise()
    return snapshot
  },
  subscribe(listener) {
    initialise()
    listeners.add(listener)
    listener(snapshot)
    return () => {
      listeners.delete(listener)
    }
  },
  async signUp(input) {
    initialise()
    const user = demoStore.signUp(input)
    setUser(user)
    return user
  },
  async signIn(input) {
    initialise()
    const user = demoStore.signIn(input)
    setUser(user)
    return user
  },
  async signOut() {
    initialise()
    demoStore.signOut()
    setUser(null)
  },
  async sendPasswordReset() {
    throw new AppError('not-implemented', {
      userMessage:
        'Password recovery is handled by Firebase Authentication and is not active in this frontend-only preview. No reset email was sent.',
    })
  },
  async isUsernameAvailable(username) {
    initialise()
    return demoStore.isUsernameAvailable(username)
  },
  listDemoAccounts() {
    return demoStore.getDemoAccounts().map((account) => account.username)
  },
}

const profiles: ProfileService = {
  async getPublicProfile(username) {
    return demoStore.getPublicProfile(username)
  },
}

const leaderboard: LeaderboardService = {
  async getActiveCompetition() {
    return demoStore.getCompetition()
  },
  async getLeaderboard() {
    return demoStore.getLeaderboard()
  },
}

const submissions: SubmissionService = {
  async getWeeklyStatus(uid) {
    return demoStore.getWeeklyStatus(uid)
  },
  async confirmSubmission(input) {
    return demoStore.confirmSubmission(input)
  },
}

const showcases: ShowcaseService = {
  async getEligibility() {
    return demoStore.getShowcaseEligibility()
  },
  async submitShowcase(input) {
    return demoStore.submitShowcase(input)
  },
}

const reports: ReportService = {
  async submitReport(input) {
    demoStore.submitReport(input)
    return { status: 'accepted' }
  },
}

const admin: AdminService = {
  async getOverview() {
    return demoStore.getAdminOverview()
  },
  async listUsers(query) {
    return demoStore.listUsers(query)
  },
  async suspendUser({ uid, reason }) {
    demoStore.suspendUser(uid, reason)
  },
  async restoreUser({ uid, reason }) {
    demoStore.restoreUser(uid, reason)
  },
  async correctScore({ uid, score, reason }) {
    demoStore.correctScore(uid, score, reason)
  },
  async removeShowcase({ uid, reason }) {
    demoStore.removeShowcase(uid, reason)
  },
  async disqualifySubmission({ uid, reason }) {
    demoStore.disqualifySubmission(uid, reason)
  },
  async restoreSubmission({ uid, reason }) {
    demoStore.restoreSubmission(uid, reason)
  },
  async removeProfilePicture({ uid, reason }) {
    demoStore.removeProfilePicture(uid, reason)
  },
  async recalculateRankings() {
    return { rankedCount: demoStore.recalculateRankings() }
  },
  async getModerationQueue() {
    return demoStore.getModerationQueue()
  },
  async resolveReport({ reportId, action }) {
    demoStore.resolveReport(reportId, action)
  },
  async getAuditEvents() {
    return demoStore.getAuditEvents()
  },
}

const media: MediaService = {
  async uploadProfilePhoto() {
    throw notImplemented('Profile photo upload')
  },
  async uploadShowcasePhoto() {
    throw notImplemented('Showcase photo upload')
  },
  async deleteShowcasePhoto() {
    throw notImplemented('Showcase photo deletion')
  },
}

export const demoBackend: Services = {
  mode: 'demo',
  auth,
  profiles,
  leaderboard,
  submissions,
  showcases,
  reports,
  admin,
  media,
}

export { demoStore }
