import type { AuthSnapshot } from '@/types/domain'
import type { Services } from '@/types/services'
import { notImplemented } from '../errors'

/**
 * PHASE 2 PLACEHOLDERS.
 *
 * These implementations intentionally fail with a clear, user-safe message.
 * Firebase Authentication, Firestore queries and trusted callable functions
 * are wired in Phase 2 (see docs/FIREBASE_PLAN.md). Nothing here pretends to
 * be working, and no service-account credentials exist in the browser bundle.
 */

const anonymous: AuthSnapshot = { status: 'anonymous', user: null }

const pending = (feature: string): never => {
  throw notImplemented(feature)
}

export const firebaseBackend: Services = {
  mode: 'firebase',
  auth: {
    async getSnapshot() {
      return anonymous
    },
    subscribe(listener) {
      listener(anonymous)
      return () => undefined
    },
    async signUp() {
      return pending('Firebase registration')
    },
    async signIn() {
      return pending('Firebase login')
    },
    async signOut() {
      /* no Firebase session exists yet */
    },
    async sendPasswordReset() {
      return pending('Firebase password recovery')
    },
    async isUsernameAvailable() {
      return pending('Username availability lookup')
    },
  },
  profiles: {
    async getPublicProfile() {
      return pending('Firestore profiles')
    },
  },
  leaderboard: {
    async getActiveCompetition() {
      return pending('Firestore competitions')
    },
    async getLeaderboard() {
      return pending('Firestore leaderboard')
    },
  },
  submissions: {
    async getWeeklyStatus() {
      return pending('Firestore weekly status')
    },
    async confirmSubmission() {
      return pending('Server-side score confirmation')
    },
  },
  showcases: {
    async getEligibility() {
      return pending('Showcase eligibility')
    },
    async submitShowcase() {
      return pending('Showcase submission')
    },
  },
  reports: {
    async submitReport() {
      return pending('Moderation reports')
    },
  },
  admin: {
    async getOverview() {
      return pending('Admin overview')
    },
    async listUsers() {
      return pending('Admin user search')
    },
    async suspendUser() {
      return pending('Account suspension')
    },
    async restoreUser() {
      return pending('Account restoration')
    },
    async correctScore() {
      return pending('Score correction')
    },
    async removeShowcase() {
      return pending('Showcase removal')
    },
    async disqualifySubmission() {
      return pending('Submission disqualification')
    },
    async restoreSubmission() {
      return pending('Submission restoration')
    },
    async removeProfilePicture() {
      return pending('Profile picture removal')
    },
    async recalculateRankings() {
      return pending('Rank recalculation')
    },
    async getModerationQueue() {
      return pending('Moderation queue')
    },
    async resolveReport() {
      return pending('Report resolution')
    },
    async getAuditEvents() {
      return pending('Admin audit log')
    },
  },
  media: {
    async uploadProfilePhoto() {
      return pending('Profile photo upload')
    },
    async uploadShowcasePhoto() {
      return pending('Showcase photo upload')
    },
    async deleteShowcasePhoto() {
      return pending('Showcase photo deletion')
    },
  },
}
