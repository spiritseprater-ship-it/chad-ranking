/**
 * DEMO-ONLY in-memory data store.
 *
 * This exists purely so the Phase 1 interface can be explored before Firebase
 * is connected. It is NOT a backend: state lives in browser memory, resets on
 * reload, and must never be described as real authentication or ranking.
 *
 * It is selected only when Firebase is not configured AND
 * VITE_ENABLE_DEMO_PREVIEW=true.
 */

import { rankTitleFor, REPORT_CATEGORIES } from '@/config/constants'
import { AppError } from '@/services/errors'
import { analyzePhotoSet, validatePhotoFile } from '@/services/scoring/localScoring'
import type {
  AdminActionType,
  AdminOverview,
  AdminUserSummary,
  AuditEvent,
  Competition,
  ConfirmSubmissionInput,
  ConfirmSubmissionResult,
  CurrentUser,
  LeaderboardEntry,
  LeaderboardView,
  ModerationReport,
  PublicProfile,
  PublicShowcase,
  ReportCategory,
  ScoreBreakdownItem,
  ShowcaseEligibility,
  WeeklyStatus,
} from '@/types/domain'
import {
  formatWeekLabel,
  getCompetitionWindow,
} from '@/utils/datetime'
import { buildRankedEntries } from '@/utils/ranking'
import { normalizeUsername, validateUsername } from '@/utils/validation'

const DEMO_PASSWORD = 'ChadDemo123'
const DEMO_EMAIL_DOMAIN = 'demo.invalid'
const RANKED_LIMIT = 100

interface DemoUserRecord {
  uid: string
  username: string
  usernameLowercase: string
  email: string
  password: string
  profileImagePath: string | null
  role: 'member' | 'admin'
  accountStatus: 'active' | 'suspended'
  createdAt: string
  seeded: boolean
}

interface DemoSubmissionRecord {
  uid: string
  competitionId: string
  confirmedScore: number
  submittedAt: string
  moderationStatus: 'clear' | 'disqualified'
  scoringVersion: string
}

interface DemoShowcaseRecord {
  uid: string
  competitionId: string
  slogan: string | null
  imageUrl: string | null
  submittedAt: string
  status: 'locked' | 'removed'
}

interface DemoReportRecord {
  id: string
  reporterUid: string
  reportedUid: string
  category: ReportCategory
  status: 'pending' | 'actioned' | 'dismissed'
  createdAt: string
}

interface DemoAuditRecord {
  id: string
  actionType: AdminActionType
  actorUid: string
  targetUid: string | null
  reason: string
  createdAt: string
}

interface DemoState {
  users: DemoUserRecord[]
  submissions: DemoSubmissionRecord[]
  showcases: DemoShowcaseRecord[]
  reports: DemoReportRecord[]
  audit: DemoAuditRecord[]
  weekId: string
  currentUid: string | null
  reportCount: number
}

const SESSION_KEY = 'chad:demo-session'

const NAMES = [
  'Rohan', 'Zaid', 'Kabir', 'Ishaan', 'Arjun', 'Dev', 'Aditya', 'Krish', 'Yash',
  'Vivaan', 'Aryan', 'Sarthak', 'Pranav', 'Harsh', 'Naman', 'Dhruv', 'Kunal',
  'Manav', 'Reyansh', 'Om', 'Jai', 'Veer', 'Siddharth', 'Ansh', 'Tanish', 'Rudra',
  'Ayaan', 'Faiz', 'Rehan', 'Imran', 'Karan', 'Nishant', 'Parth', 'Raghav',
  'Sahil', 'Tarun', 'Uday', 'Varun', 'Yuvraj', 'Zayan', 'Abhay', 'Advik', 'Ahaan',
  'Akash', 'Aniket', 'Arnav', 'Atharv', 'Bhavya', 'Chirag', 'Daksh', 'Eshan',
  'Fardeen', 'Gaurav', 'Hrithik', 'Irfan', 'Jatin', 'Kian', 'Lakshya', 'Madhav',
  'Mihir', 'Neel', 'Ojas', 'Prithvi', 'Qadir', 'Ritvik', 'Samar', 'Tejas',
  'Utkarsh', 'Vedant', 'Yashwant', 'Zohair', 'Aarav', 'Abhinav', 'Amay', 'Anuj',
  'Aravind', 'Brij', 'Chetan', 'Deepak', 'Divyansh', 'Farhan', 'Gagan', 'Hardik',
  'Hemant', 'Iqbal', 'Jeevan', 'Kaushal', 'Lavish', 'Mohit', 'Nitin', 'Omesh',
  'Piyush', 'Ranveer', 'Shubh', 'Shivam', 'Tanmay', 'Ujjwal', 'Vikram', 'Vinay',
  'Yashas', 'Zubin', 'Adil', 'Bhavesh', 'Cyrus', 'Darsh', 'Eklavya', 'Girish',
  'Jitesh', 'Karthik', 'Meet', 'Nakul', 'Purav', 'Ronit', 'Sagar', 'Saharsh',
  'Teerth', 'Vansh', 'Aman', 'Arav', 'Ayush', 'Balraj', 'Devansh', 'Dheeraj',
  'Garv', 'Harish', 'Hitesh', 'Jugal', 'Kush', 'Laksh', 'Mahesh', 'Naveen',
  'Pranay', 'Rishabh', 'Sarthik', 'Shrey', 'Sourav', 'Taha', 'Viren', 'Yohan',
]

const SUFFIXES = ['_07', 'K', '_23', 'S', '_9', 'X', '_04', '_11', 'R', '_18']

const SLOGANS: Record<string, string> = {
  Rohan: 'Calm under pressure. Built for the week.',
  Zaid: 'Born to lead, not to follow.',
  Kabir: 'The standard was set before the photos.',
  Ishaan: 'Same mirror. New ranking.',
  Arjun: 'Quiet confidence, loud results.',
  Dev: 'Not the loudest. Just first.',
}

function hashString(value: string): number {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function mulberry32(seed: number): () => number {
  let state = seed
  return () => {
    state |= 0
    state = (state + 0x6d2b79f5) | 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function uidFor(username: string): string {
  return `demo-${hashString(username.toLowerCase()).toString(36)}-${normalizeUsername(username).length}`
}

function readSession(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

function writeSession(uid: string | null): void {
  try {
    if (uid) sessionStorage.setItem(SESSION_KEY, uid)
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    /* ignore storage restrictions */
  }
}

function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString()
}

function daysAgo(days: number): string {
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString()
}

function createUsers(): DemoUserRecord[] {
  const users: DemoUserRecord[] = []
  const seen = new Set<string>()
  const addUser = (username: string, options: Partial<DemoUserRecord> = {}) => {
    const lower = normalizeUsername(username)
    if (seen.has(lower)) return
    seen.add(lower)
    const base: DemoUserRecord = {
      uid: uidFor(username),
      username,
      usernameLowercase: lower,
      email: `${lower}@${DEMO_EMAIL_DOMAIN}`,
      password: DEMO_PASSWORD,
      profileImagePath: null,
      role: 'member',
      accountStatus: 'active',
      createdAt: daysAgo(12 + (users.length % 40)),
      seeded: true,
      ...options,
    }
    users.push(base)
  }

  NAMES.slice(0, 100).forEach((name) => addUser(name))
  NAMES.slice(100).forEach((name, index) => {
    const suffix = SUFFIXES[index % SUFFIXES.length] ?? ''
    addUser(`${name}${suffix}`)
  })

  addUser('RohitOfficial', { accountStatus: 'suspended', createdAt: daysAgo(3) })
  addUser('Challenger', {
    uid: 'demo-challenger',
    role: 'member',
    createdAt: daysAgo(1),
  })
  addUser('Aarav_Admin', {
    uid: 'demo-admin',
    role: 'admin',
    createdAt: daysAgo(45),
  })

  const aarav = users.find((user) => user.username === 'Aarav')
  if (aarav) aarav.role = 'admin'

  return users
}

const DEMO_USERS = createUsers()

function currentWindow() {
  return getCompetitionWindow(new Date())
}

function competitionRecord(): Competition {
  const window = currentWindow()
  return {
    id: window.id,
    weekLabel: formatWeekLabel(window.startsAt),
    startsAt: window.startsAt.toISOString(),
    endsAt: window.endsAt.toISOString(),
    status: 'active',
    timezone: 'Asia/Kolkata',
  }
}

function state(): DemoState {
  if (!demoState) {
    demoState = {
      users: DEMO_USERS,
      submissions: [],
      showcases: [],
      reports: [],
      audit: [],
      weekId: '',
      currentUid: null,
      reportCount: 0,
    }
    ensureWeek(demoState)
    const storedUid = readSession()
    if (storedUid && demoState.users.some((user) => user.uid === storedUid)) {
      demoState.currentUid = storedUid
    }
  }
  return demoState
}

let demoState: DemoState | null = null

function seedWeek(target: DemoState): void {
  const window = currentWindow()
  const competitionId = window.id
  const start = window.startsAt.getTime()
  const random = mulberry32(hashString(competitionId))

  const explicit: Record<string, number> = {
    Rohan: 99,
    Zaid: 98,
    Kabir: 97,
    Ishaan: 96,
    Arjun: 95,
    Dev: 94,
    Aditya: 94,
    Krish: 93,
    Yash: 93,
    Vivaan: 92,
    Aarav: 78,
    Aarav_Admin: 74,
  }

  target.submissions = []
  target.showcases = []
  target.reports = []
  target.audit = []

  const participants = target.users.filter(
    (user) =>
      user.username !== 'Challenger' &&
      user.username !== 'RohitOfficial' &&
      user.seeded,
  )

  participants.forEach((user, index) => {
    const explicitScore = explicit[user.username]
    const score =
      explicitScore !== undefined
        ? explicitScore
        : Math.round(66 + random() * 25)
    const submittedAt = new Date(
      start + (index * 37 + Math.floor(random() * 30)) * 60 * 1000,
    ).toISOString()
    target.submissions.push({
      uid: user.uid,
      competitionId,
      confirmedScore: score,
      submittedAt,
      moderationStatus: 'clear',
      scoringVersion: 'local-heuristic-v1',
    })
  })

  const rohit = target.users.find((user) => user.username === 'RohitOfficial')
  if (rohit) {
    target.submissions.push({
      uid: rohit.uid,
      competitionId,
      confirmedScore: 97,
      submittedAt: new Date(start + 90 * 60 * 1000).toISOString(),
      moderationStatus: 'clear',
      scoringVersion: 'local-heuristic-v1',
    })
  }

  const ranked = buildRankedEntries(
    target.submissions
      .filter((submission) => submission.moderationStatus === 'clear')
      .map((submission) => {
        const user = target.users.find((item) => item.uid === submission.uid)
        return {
          uid: submission.uid,
          username: user?.username ?? 'Unknown',
          profileImagePath: user?.profileImagePath ?? null,
          score: submission.confirmedScore,
          submittedAt: submission.submittedAt,
        }
      }),
    RANKED_LIMIT,
  ).ranked

  ranked.slice(0, 6).forEach((entry, index) => {
    target.showcases.push({
      uid: entry.uid,
      competitionId,
      slogan: SLOGANS[entry.username] ?? 'Here for the week.',
      imageUrl: null,
      submittedAt: new Date(
        new Date(entry.submittedAt).getTime() + (index + 1) * 45 * 60 * 1000,
      ).toISOString(),
      status: 'locked',
    })
  })

  const reporters = target.users.filter((user) => user.username !== 'Challenger')
  const reportSubjects = ['RohitOfficial', 'Kabir', 'Kunal_07']
  const categories: ReportCategory[] = [
    'impersonation',
    'inappropriate-image',
    'fake-profile',
  ]
  reportSubjects.forEach((username, index) => {
    const reported = target.users.find((user) => user.username === username)
    const reporter = reporters[index * 7]
    if (!reported || !reporter) return
    target.reports.push({
      id: `demo-report-${index + 1}`,
      reporterUid: reporter.uid,
      reportedUid: reported.uid,
      category: categories[index] ?? 'spam',
      status: index === 2 ? 'dismissed' : 'pending',
      createdAt: hoursAgo(index === 0 ? 2 : index === 1 ? 6 : 26),
    })
  })

  target.audit = [
    {
      id: 'demo-audit-1',
      actionType: 'score-correction',
      actorUid: 'demo-admin',
      targetUid: target.users.find((user) => user.username === 'Kunal')?.uid ?? null,
      reason: 'Corrected a misread analysis after manual review.',
      createdAt: daysAgo(1),
    },
    {
      id: 'demo-audit-2',
      actionType: 'user-suspended',
      actorUid: 'demo-admin',
      targetUid: rohit?.uid ?? null,
      reason: 'Reported impersonation; pending final review.',
      createdAt: hoursAgo(20),
    },
  ]
}

function ensureWeek(target: DemoState): void {
  const competitionId = currentWindow().id
  if (target.weekId === competitionId) return
  target.showcases.forEach((showcase) => {
    if (showcase.imageUrl) URL.revokeObjectURL(showcase.imageUrl)
  })
  target.weekId = competitionId
  seedWeek(target)
}

function findUserByUid(target: DemoState, uid: string): DemoUserRecord {
  const user = target.users.find((item) => item.uid === uid)
  if (!user) {
    throw new AppError('not-found', { userMessage: 'This account no longer exists.' })
  }
  return user
}

function currentUser(target: DemoState): DemoUserRecord {
  if (!target.currentUid) throw new AppError('not-authenticated')
  return findUserByUid(target, target.currentUid)
}

function requireAdmin(target: DemoState): DemoUserRecord {
  const user = currentUser(target)
  if (user.role !== 'admin' || user.accountStatus !== 'active') {
    throw new AppError('forbidden', {
      userMessage: 'Administrator access is required for that action.',
    })
  }
  return user
}

function toCurrentUser(user: DemoUserRecord): CurrentUser {
  return {
    uid: user.uid,
    username: user.username,
    profileImagePath: user.profileImagePath,
    role: user.role,
    accountStatus: user.accountStatus,
    createdAt: user.createdAt,
  }
}

function toAdminSummary(
  target: DemoState,
  user: DemoUserRecord,
  leaderboard: LeaderboardView,
): AdminUserSummary {
  const entry = leaderboard.ranked.find((item) => item.uid === user.uid)
  const submission = target.submissions.find(
    (item) =>
      item.uid === user.uid && item.competitionId === leaderboard.competition.id,
  )
  const showcase = target.showcases.find(
    (item) =>
      item.uid === user.uid &&
      item.competitionId === leaderboard.competition.id &&
      item.status === 'locked',
  )
  return {
    uid: user.uid,
    username: user.username,
    createdAt: user.createdAt,
    accountStatus: user.accountStatus,
    role: user.role,
    confirmedScore: entry?.score ?? submission?.confirmedScore ?? null,
    rank: entry?.rank ?? null,
    moderationStatus: submission?.moderationStatus ?? 'clear',
    hasShowcase: Boolean(showcase),
  }
}

function requireReason(reason: string): string {
  const cleaned = reason.trim()
  if (cleaned.length < 3) {
    throw new AppError('forbidden', {
      userMessage: 'Record a short reason (at least 3 characters) for this action.',
    })
  }
  return cleaned
}

function appendAudit(
  target: DemoState,
  actionType: AdminActionType,
  actor: DemoUserRecord,
  targetUid: string | null,
  reason: string,
): void {
  target.audit.unshift({
    id: `demo-audit-${Date.now()}-${target.audit.length}`,
    actionType,
    actorUid: actor.uid,
    targetUid,
    reason,
    createdAt: new Date().toISOString(),
  })
}

const ACTION_LABELS: Record<AdminActionType, string> = {
  'score-correction': 'Score corrected',
  'user-suspended': 'Account suspended',
  'user-restored': 'Account restored',
  'showcase-removed': 'Showcase removed',
  'submission-disqualified': 'Submission disqualified',
  'profile-picture-removed': 'Profile picture removed',
  'admin-role-granted': 'Admin access granted',
  'admin-role-revoked': 'Admin access revoked',
  'report-dismissed': 'Report dismissed',
  'report-actioned': 'Report actioned',
  'rankings-recalculated': 'Rankings recalculated',
  'competition-reset': 'Competition reset',
}

function toAuditEvent(target: DemoState, record: DemoAuditRecord): AuditEvent {
  const actor = target.users.find((user) => user.uid === record.actorUid)
  const subject = record.targetUid
    ? target.users.find((user) => user.uid === record.targetUid)
    : null
  return {
    id: record.id,
    actionType: record.actionType,
    actionLabel: ACTION_LABELS[record.actionType],
    actorUid: record.actorUid,
    actorUsername: actor?.username ?? 'Unknown admin',
    targetUid: record.targetUid,
    targetUsername: subject?.username ?? null,
    reason: record.reason,
    createdAt: record.createdAt,
  }
}

/* ------------------------------------------------------------------------- */
/* Public demo store API                                                      */
/* ------------------------------------------------------------------------- */

export const demoStore = {
  getSnapshot() {
    const target = state()
    ensureWeek(target)
    const user = target.currentUid
      ? target.users.find((item) => item.uid === target.currentUid) ?? null
      : null
    return { user: user ? toCurrentUser(user) : null }
  },

  getDemoAccounts(): Array<{ username: string; role: 'member' | 'admin'; note: string }> {
    return [
      { username: 'Challenger', role: 'member', note: 'Unranked — try the full flow' },
      { username: 'Zaid', role: 'member', note: 'Top 10 — showcase unlocked' },
      { username: 'Aarav_Admin', role: 'admin', note: 'Administrator' },
    ]
  },

  demoPassword: DEMO_PASSWORD,

  async changePassword(): Promise<void> {
    throw new AppError('not-implemented', {
      userMessage:
        'Password changes require Firebase Authentication (Phase 2). No local password was changed.',
    })
  },

  signUp(input: {
    username: string
    email: string
    password: string
  }): CurrentUser {
    const target = state()
    ensureWeek(target)
    const usernameCheck = validateUsername(input.username)
    if (!usernameCheck.valid) {
      throw new AppError('username-invalid', { userMessage: usernameCheck.message })
    }
    const lower = normalizeUsername(input.username)
    if (target.users.some((user) => user.usernameLowercase === lower)) {
      throw new AppError('username-taken')
    }
    if (target.users.some((user) => user.email === input.email.toLowerCase())) {
      throw new AppError('email-in-use')
    }
    if (input.password.length < 8) {
      throw new AppError('weak-password')
    }
    const record: DemoUserRecord = {
      uid: `demo-user-${Date.now().toString(36)}`,
      username: input.username.trim(),
      usernameLowercase: lower,
      email: input.email.trim().toLowerCase(),
      password: input.password,
      profileImagePath: null,
      role: 'member',
      accountStatus: 'active',
      createdAt: new Date().toISOString(),
      seeded: false,
    }
    target.users.push(record)
    target.currentUid = record.uid
    writeSession(record.uid)
    return toCurrentUser(record)
  },

  signIn(input: { identifier: string; password: string }): CurrentUser {
    const target = state()
    ensureWeek(target)
    const identifier = input.identifier.trim()
    const user = target.users.find(
      (item) =>
        item.usernameLowercase === normalizeUsername(identifier) ||
        item.email === identifier.toLowerCase(),
    )
    if (!user || user.password !== input.password) {
      throw new AppError('invalid-credentials')
    }
    if (user.accountStatus === 'suspended') {
      throw new AppError('forbidden', {
        userMessage:
          'This account is suspended. Contact an administrator if you believe this is a mistake.',
      })
    }
    target.currentUid = user.uid
    writeSession(user.uid)
    return toCurrentUser(user)
  },

  signOut(): void {
    const target = state()
    target.currentUid = null
    writeSession(null)
  },

  isUsernameAvailable(username: string): boolean {
    const target = state()
    const lower = normalizeUsername(username)
    return !target.users.some((user) => user.usernameLowercase === lower)
  },

  getCompetition(): Competition {
    return competitionRecord()
  },

  getLeaderboard(): LeaderboardView {
    const target = state()
    ensureWeek(target)
    const competition = competitionRecord()
    const activeUsers = target.users.filter((user) => user.accountStatus === 'active')
    const confirmed = target.submissions.filter((submission) => {
      if (submission.competitionId !== competition.id) return false
      if (submission.moderationStatus !== 'clear') return false
      const owner = target.users.find((user) => user.uid === submission.uid)
      return owner?.accountStatus === 'active'
    })
    const { ranked, directory } = buildRankedEntries(
      confirmed.map((submission) => {
        const user = target.users.find((item) => item.uid === submission.uid)
        return {
          uid: submission.uid,
          username: user?.username ?? 'Unknown',
          profileImagePath: user?.profileImagePath ?? null,
          score: submission.confirmedScore,
          submittedAt: submission.submittedAt,
        }
      }),
      RANKED_LIMIT,
    )
    const confirmedUids = new Set(confirmed.map((item) => item.uid))
    const unconfirmedCount = activeUsers.filter(
      (user) => !confirmedUids.has(user.uid),
    ).length

    return {
      competition,
      ranked,
      directory,
      unconfirmedCount,
      totalParticipants: confirmed.length,
      generatedAt: new Date().toISOString(),
    }
  },

  getPublicProfile(username: string): PublicProfile {
    const target = state()
    ensureWeek(target)
    const user = target.users.find(
      (item) => item.usernameLowercase === normalizeUsername(username),
    )
    if (!user) {
      throw new AppError('not-found', {
        userMessage: 'No participant exists with that username.',
      })
    }
    const leaderboard = demoStore.getLeaderboard()
    const entry = leaderboard.ranked.find((item) => item.uid === user.uid)
    const directoryEntry = leaderboard.directory.find((item) => item.uid === user.uid)
    const rank = entry?.rank ?? directoryEntry?.rank ?? null
    const score = entry?.score ?? null
    const eligible = rank !== null && rank <= 10 && user.accountStatus === 'active'
    const showcaseRecord = target.showcases.find(
      (item) =>
        item.uid === user.uid &&
        item.competitionId === leaderboard.competition.id &&
        item.status === 'locked',
    )
    const showcase: PublicShowcase | null =
      eligible && showcaseRecord && entry
        ? {
            slogan: showcaseRecord.slogan,
            imagePath: showcaseRecord.imageUrl,
            rank: entry.rank,
            title: entry.title,
            submittedAt: showcaseRecord.submittedAt,
            locked: true,
          }
        : null

    return {
      uid: user.uid,
      username: user.username,
      profileImagePath: user.profileImagePath,
      accountStatus: user.accountStatus,
      createdAt: user.createdAt,
      competitionId: leaderboard.competition.id,
      score: user.accountStatus === 'active' ? score : null,
      rank: user.accountStatus === 'active' ? rank : null,
      title: rank === null ? 'NOT YET RANKED' : rankTitleFor(rank),
      showcase,
      isSelf: target.currentUid === user.uid,
    }
  },

  getWeeklyStatus(uid: string): WeeklyStatus {
    const target = state()
    ensureWeek(target)
    const leaderboard = demoStore.getLeaderboard()
    const user = findUserByUid(target, uid)
    const submission = target.submissions.find(
      (item) => item.uid === uid && item.competitionId === leaderboard.competition.id,
    )
    const entry = leaderboard.ranked.find((item) => item.uid === uid)
    const directoryEntry = leaderboard.directory.find((item) => item.uid === uid)
    const rank = entry?.rank ?? directoryEntry?.rank ?? null
    const confirmed = submission !== undefined && submission.moderationStatus === 'clear'

    let blockedReason: string | null = null
    if (user.accountStatus !== 'active') {
      blockedReason = 'This account is suspended and cannot enter this week’s competition.'
    } else if (submission?.moderationStatus === 'disqualified') {
      blockedReason =
        'This week’s submission was disqualified after moderation. Contact an administrator.'
    } else if (confirmed) {
      blockedReason =
        'Your score is confirmed and locked for this week. The next competition opens Monday at 00:00 IST.'
    }

    return {
      competition: leaderboard.competition,
      submission: submission
        ? {
            uid,
            competitionId: submission.competitionId,
            confirmedScore: submission.confirmedScore,
            status: submission.moderationStatus === 'disqualified' ? 'none' : 'confirmed',
            submittedAt: submission.submittedAt,
            scoringVersion: submission.scoringVersion,
            moderationStatus: submission.moderationStatus,
            locked: true,
            attemptsUsed: 1,
            attemptsAllowed: 1,
          }
        : null,
      rank,
      title: rank !== null ? (entry?.title ?? 'UNRANKED') : 'UNRANKED',
      canSubmit: blockedReason === null,
      canRetry: false,
      blockedReason,
    }
  },

  async analyzeProvisional(files: File[]): Promise<{
    provisional: Awaited<ReturnType<typeof analyzePhotoSet>>
    breakdown: ScoreBreakdownItem[]
  }> {
    const provisional = await analyzePhotoSet(files)
    return { provisional, breakdown: provisional.breakdown }
  },

  async confirmSubmission(
    input: ConfirmSubmissionInput,
  ): Promise<ConfirmSubmissionResult> {
    const target = state()
    ensureWeek(target)
    const user = currentUser(target)
    const competition = competitionRecord()

    if (input.competitionId !== competition.id) {
      throw new AppError('competition-expired')
    }
    if (user.accountStatus !== 'active') {
      throw new AppError('forbidden', {
        userMessage: 'Suspended accounts cannot confirm a submission.',
      })
    }
    if (!Number.isInteger(input.score) || input.score < 0 || input.score > 100) {
      throw new AppError('invalid-image', {
        userMessage: 'The score must be a whole number between 0 and 100.',
      })
    }
    const existing = target.submissions.find(
      (item) => item.uid === user.uid && item.competitionId === competition.id,
    )
    if (existing && existing.moderationStatus === 'clear') {
      throw new AppError('already-confirmed')
    }

    target.submissions = target.submissions.filter(
      (item) => !(item.uid === user.uid && item.competitionId === competition.id),
    )
    target.submissions.push({
      uid: user.uid,
      competitionId: competition.id,
      confirmedScore: input.score,
      submittedAt: new Date().toISOString(),
      moderationStatus: 'clear',
      scoringVersion: input.scoringVersion,
    })

    const leaderboard = demoStore.getLeaderboard()
    const entry = leaderboard.ranked.find((item) => item.uid === user.uid)
    const directoryEntry = leaderboard.directory.find((item) => item.uid === user.uid)
    const rank = entry?.rank ?? directoryEntry?.rank ?? null
    if (rank === null) {
      throw new AppError('unknown', {
        userMessage: 'Your score was saved, but the rank could not be read. Refresh the leaderboard.',
      })
    }

    return {
      score: input.score,
      rank,
      title: entry?.title ?? 'UNRANKED',
      showcaseEligible: rank <= 10,
      lockedUntil: competition.endsAt,
    }
  },

  getShowcaseEligibility(): ShowcaseEligibility {
    const target = state()
    ensureWeek(target)
    const user = currentUser(target)
    const leaderboard = demoStore.getLeaderboard()
    const entry = leaderboard.ranked.find((item) => item.uid === user.uid)
    const rank = entry?.rank ?? null
    const eligible = rank !== null && rank <= 10 && user.accountStatus === 'active'
    const record = target.showcases.find(
      (item) =>
        item.uid === user.uid &&
        item.competitionId === leaderboard.competition.id &&
        item.status === 'locked',
    )

    return {
      competitionId: leaderboard.competition.id,
      rank,
      score: entry?.score ?? null,
      eligible,
      showcase: eligible && entry && record
        ? {
            slogan: record.slogan,
            imagePath: record.imageUrl,
            rank: entry.rank,
            title: entry.title,
            submittedAt: record.submittedAt,
            locked: true,
          }
        : null,
      reason:
        rank === null
          ? 'Confirm a score this week to become eligible for the showcase.'
          : rank > 10
            ? 'Only the current Top 10 can submit a showcase. Keep climbing.'
            : record
              ? 'Your showcase is locked for the rest of this week.'
              : null,
    }
  },

  async submitShowcase(input: {
    slogan: string
    imageFile: File | null
  }): Promise<void> {
    const target = state()
    ensureWeek(target)
    const user = currentUser(target)
    const eligibility = demoStore.getShowcaseEligibility()
    if (!eligibility.eligible) {
      throw new AppError('not-eligible', {
        userMessage: eligibility.reason ?? undefined,
      })
    }
    if (eligibility.showcase) {
      throw new AppError('showcase-locked')
    }
    const slogan = input.slogan.trim()
    if (slogan.length > 120) {
      throw new AppError('invalid-image', {
        userMessage: 'Keep your slogan to 120 characters or fewer.',
      })
    }
    let imageUrl: string | null = null
    if (input.imageFile) {
      validatePhotoFile(input.imageFile)
      imageUrl = URL.createObjectURL(input.imageFile)
    }

    target.showcases.push({
      uid: user.uid,
      competitionId: eligibility.competitionId,
      slogan: slogan.length > 0 ? slogan : null,
      imageUrl,
      submittedAt: new Date().toISOString(),
      status: 'locked',
    })
  },

  submitReport(input: {
    reportedUid: string
    category: ReportCategory
  }): void {
    const target = state()
    ensureWeek(target)
    const reporter = currentUser(target)
    if (target.reportCount >= 5) {
      throw new AppError('rate-limited', {
        userMessage: 'You have submitted several reports in this session. Try again later.',
      })
    }
    const reported = findUserByUid(target, input.reportedUid)
    if (reported.uid === reporter.uid) {
      throw new AppError('forbidden', {
        userMessage: 'You cannot report your own profile.',
      })
    }
    const duplicate = target.reports.some(
      (report) =>
        report.reporterUid === reporter.uid &&
        report.reportedUid === reported.uid &&
        report.status === 'pending',
    )
    if (duplicate) throw new AppError('duplicate-report')

    target.reports.unshift({
      id: `demo-report-${Date.now()}`,
      reporterUid: reporter.uid,
      reportedUid: reported.uid,
      category: input.category,
      status: 'pending',
      createdAt: new Date().toISOString(),
    })
    target.reportCount += 1
  },

  getAdminOverview(): AdminOverview {
    const target = state()
    ensureWeek(target)
    requireAdmin(target)
    const leaderboard = demoStore.getLeaderboard()
    const pendingReports = demoStore.getModerationQueue().filter(
      (report) => report.status === 'pending',
    )
    return {
      stats: {
        totalUsers: target.users.length,
        activeParticipants: leaderboard.totalParticipants,
        rankedCount: leaderboard.ranked.length,
        belowCutoffCount: leaderboard.directory.length,
        topTenCount: leaderboard.ranked.slice(0, 10).length,
        pendingReports: pendingReports.length,
        suspendedCount: target.users.filter(
          (user) => user.accountStatus === 'suspended',
        ).length,
        competitionId: leaderboard.competition.id,
        generatedAt: new Date().toISOString(),
      },
      competition: leaderboard.competition,
      topTen: leaderboard.ranked.slice(0, 10),
      pendingReports,
      recentAudit: demoStore.getAuditEvents().slice(0, 5),
    }
  },

  listUsers(query = ''): AdminUserSummary[] {
    const target = state()
    ensureWeek(target)
    requireAdmin(target)
    const leaderboard = demoStore.getLeaderboard()
    const needle = normalizeUsername(query)
    return target.users
      .filter(
        (user) =>
          needle.length === 0 || user.usernameLowercase.includes(needle),
      )
      .map((user) => toAdminSummary(target, user, leaderboard))
      .sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999))
  },

  suspendUser(uid: string, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    const user = findUserByUid(target, uid)
    if (user.uid === admin.uid) {
      throw new AppError('forbidden', {
        userMessage: 'You cannot suspend your own administrator account.',
      })
    }
    user.accountStatus = 'suspended'
    appendAudit(target, 'user-suspended', admin, uid, requireReason(reason))
  },

  restoreUser(uid: string, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    const user = findUserByUid(target, uid)
    user.accountStatus = 'active'
    appendAudit(target, 'user-restored', admin, uid, requireReason(reason))
  },

  correctScore(uid: string, score: number, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    if (!Number.isInteger(score) || score < 0 || score > 100) {
      throw new AppError('invalid-image', {
        userMessage: 'Scores must be whole numbers from 0 to 100.',
      })
    }
    const competition = competitionRecord()
    const submission = target.submissions.find(
      (item) => item.uid === uid && item.competitionId === competition.id,
    )
    if (!submission) {
      throw new AppError('not-found', {
        userMessage: 'That participant has no confirmed submission this week.',
      })
    }
    submission.confirmedScore = score
    appendAudit(target, 'score-correction', admin, uid, requireReason(reason))
  },

  removeShowcase(uid: string, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    const competition = competitionRecord()
    const showcase = target.showcases.find(
      (item) => item.uid === uid && item.competitionId === competition.id,
    )
    if (showcase) {
      if (showcase.imageUrl) URL.revokeObjectURL(showcase.imageUrl)
      target.showcases = target.showcases.filter((item) => item !== showcase)
    }
    appendAudit(target, 'showcase-removed', admin, uid, requireReason(reason))
  },

  disqualifySubmission(uid: string, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    const competition = competitionRecord()
    const submission = target.submissions.find(
      (item) => item.uid === uid && item.competitionId === competition.id,
    )
    if (!submission) throw new AppError('not-found')
    submission.moderationStatus = 'disqualified'
    const showcase = target.showcases.find(
      (item) => item.uid === uid && item.competitionId === competition.id,
    )
    if (showcase) {
      if (showcase.imageUrl) URL.revokeObjectURL(showcase.imageUrl)
      target.showcases = target.showcases.filter((item) => item !== showcase)
    }
    appendAudit(target, 'submission-disqualified', admin, uid, requireReason(reason))
  },

  restoreSubmission(uid: string, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    const competition = competitionRecord()
    const submission = target.submissions.find(
      (item) => item.uid === uid && item.competitionId === competition.id,
    )
    if (!submission) throw new AppError('not-found')
    submission.moderationStatus = 'clear'
    appendAudit(target, 'rankings-recalculated', admin, uid, requireReason(reason))
  },

  removeProfilePicture(uid: string, reason: string): void {
    const target = state()
    const admin = requireAdmin(target)
    const user = findUserByUid(target, uid)
    user.profileImagePath = null
    appendAudit(target, 'profile-picture-removed', admin, uid, requireReason(reason))
  },

  recalculateRankings(): number {
    const target = state()
    const admin = requireAdmin(target)
    appendAudit(target, 'rankings-recalculated', admin, null, 'Manual recalculation check.')
    return demoStore.getLeaderboard().ranked.length
  },

  getModerationQueue(): ModerationReport[] {
    const target = state()
    ensureWeek(target)
    requireAdmin(target)
    return target.reports
      .map((report) => {
        const reporter = target.users.find((user) => user.uid === report.reporterUid)
        const reported = target.users.find((user) => user.uid === report.reportedUid)
        const category = REPORT_CATEGORIES.find(
          (option) => option.value === report.category,
        )
        return {
          id: report.id,
          reporterUid: report.reporterUid,
          reporterUsername: reporter?.username ?? 'Unknown',
          reportedUid: report.reportedUid,
          reportedUsername: reported?.username ?? 'Unknown',
          category: report.category,
          categoryLabel: category?.label ?? 'Report',
          status: report.status,
          createdAt: report.createdAt,
        }
      })
      .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
  },

  resolveReport(reportId: string, action: 'actioned' | 'dismissed'): void {
    const target = state()
    const admin = requireAdmin(target)
    const report = target.reports.find((item) => item.id === reportId)
    if (!report) throw new AppError('not-found')
    report.status = action
    appendAudit(
      target,
      action === 'dismissed' ? 'report-dismissed' : 'report-actioned',
      admin,
      report.reportedUid,
      action === 'dismissed'
        ? 'Report reviewed and dismissed.'
        : 'Report reviewed; moderation action recorded.',
    )
  },

  getAuditEvents(): AuditEvent[] {
    const target = state()
    requireAdmin(target)
    return target.audit
      .map((record) => toAuditEvent(target, record))
      .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
  },

  getCurrentUser(): CurrentUser | null {
    return demoStore.getSnapshot().user
  },

  getRankedEntry(uid: string): LeaderboardEntry | null {
    return demoStore.getLeaderboard().ranked.find((entry) => entry.uid === uid) ?? null
  },
}
