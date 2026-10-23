import type { AuthSnapshot } from '@/types/domain'
import type { Services } from '@/types/services'
import { backendUnconfigured } from './errors'

const anonymous: AuthSnapshot = { status: 'anonymous', user: null }

/**
 * Used when Firebase is not configured and the demo preview is disabled.
 * Every privileged action fails loudly instead of inventing local data.
 */
export const unconfiguredBackend: Services = {
  mode: 'unconfigured',
  auth: {
    async getSnapshot() {
      return anonymous
    },
    subscribe(listener) {
      listener(anonymous)
      return () => undefined
    },
    async signUp() {
      throw backendUnconfigured()
    },
    async signIn() {
      throw backendUnconfigured()
    },
    async signOut() {
      /* nothing to sign out of */
    },
    async sendPasswordReset() {
      throw backendUnconfigured()
    },
    async isUsernameAvailable() {
      throw backendUnconfigured()
    },
  },
  profiles: {
    async getPublicProfile() {
      throw backendUnconfigured()
    },
  },
  leaderboard: {
    async getActiveCompetition() {
      throw backendUnconfigured()
    },
    async getLeaderboard() {
      throw backendUnconfigured()
    },
  },
  submissions: {
    async getWeeklyStatus() {
      throw backendUnconfigured()
    },
    async confirmSubmission() {
      throw backendUnconfigured()
    },
  },
  showcases: {
    async getEligibility() {
      throw backendUnconfigured()
    },
    async submitShowcase() {
      throw backendUnconfigured()
    },
  },
  reports: {
    async submitReport() {
      throw backendUnconfigured()
    },
  },
  admin: {
    async getOverview() {
      throw backendUnconfigured()
    },
    async listUsers() {
      throw backendUnconfigured()
    },
    async suspendUser() {
      throw backendUnconfigured()
    },
    async restoreUser() {
      throw backendUnconfigured()
    },
    async correctScore() {
      throw backendUnconfigured()
    },
    async removeShowcase() {
      throw backendUnconfigured()
    },
    async disqualifySubmission() {
      throw backendUnconfigured()
    },
    async restoreSubmission() {
      throw backendUnconfigured()
    },
    async removeProfilePicture() {
      throw backendUnconfigured()
    },
    async recalculateRankings() {
      throw backendUnconfigured()
    },
    async getModerationQueue() {
      throw backendUnconfigured()
    },
    async resolveReport() {
      throw backendUnconfigured()
    },
    async getAuditEvents() {
      throw backendUnconfigured()
    },
  },
  media: {
    async uploadProfilePhoto() {
      throw backendUnconfigured()
    },
    async uploadShowcasePhoto() {
      throw backendUnconfigured()
    },
    async deleteShowcasePhoto() {
      throw backendUnconfigured()
    },
  },
}
