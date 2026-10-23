/**
 * Firestore Security Rules tests — Phase 2, step 1.
 *
 * Runs against the Firebase Emulator Suite (no project, no credentials, no
 * billing). Every privileged write is attempted from a real client SDK, so a
 * rule regression fails CI instead of silently shipping.
 *
 *   npm run test:rules
 *
 * Project ID is a `demo-*` id: the emulator never contacts production.
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'
import { after, beforeEach, describe, it } from 'node:test'

import {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
} from '@firebase/rules-unit-testing'
import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  limit,
  query,
  serverTimestamp,
  setDoc,
  Timestamp,
  updateDoc,
  where,
  writeBatch,
} from 'firebase/firestore'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '../..')
const [host, port] = (process.env.FIRESTORE_EMULATOR_HOST ?? '127.0.0.1:8080').split(':')

const testEnv = await initializeTestEnvironment({
  projectId: 'demo-chad-ranking',
  firestore: {
    rules: readFileSync(resolve(repoRoot, 'firestore.rules'), 'utf8'),
    host,
    port: Number(port ?? 8080),
  },
})

const asUser = (uid) => testEnv.authenticatedContext(uid).firestore()
const asAnon = () => testEnv.unauthenticatedContext().firestore()

/** Writes a trusted document, bypassing rules — mirrors the Cloudflare Worker. */
async function seedDoc(path, data) {
  await testEnv.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), path), data)
  })
}

function profile(uid, username, overrides = {}) {
  return {
    uid,
    username,
    usernameLowercase: username.toLowerCase(),
    profileImagePath: null,
    createdAt: Timestamp.now(),
    role: 'member',
    accountStatus: 'active',
    ...overrides,
  }
}

function avatar(uid, overrides = {}) {
  return {
    uid,
    mime: 'image/webp',
    data: 'A'.repeat(2048),
    bytes: 1536,
    width: 256,
    height: 256,
    updatedAt: serverTimestamp(),
    ...overrides,
  }
}

function submission(uid, competitionId, overrides = {}) {
  return {
    uid,
    competitionId,
    confirmedScore: 87,
    breakdown: { pose: 90, expression: 88, creativity: 84, styling: 85 },
    submittedAt: Timestamp.now(),
    scoringVersion: 'local-heuristic-v1',
    evidenceHash: 'a'.repeat(64),
    moderationStatus: 'clear',
    disqualificationReason: null,
    ...overrides,
  }
}

beforeEach(async () => {
  await testEnv.clearFirestore()
})

after(async () => {
  await testEnv.cleanup()
})

describe('users', () => {
  it('lets anyone read a public profile', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    const snapshot = await assertSucceeds(getDoc(doc(asAnon(), 'users/member1')))
    assert.equal(snapshot.data().username, 'Rohan')
  })

  it('creates the profile and its username reservation atomically', async () => {
    const db = asUser('member1')
    const batch = writeBatch(db)
    batch.set(doc(db, 'usernames/rohan'), {
      uid: 'member1',
      usernameLowercase: 'rohan',
      createdAt: serverTimestamp(),
    })
    batch.set(doc(db, 'users/member1'), {
      uid: 'member1',
      username: 'Rohan',
      usernameLowercase: 'rohan',
      profileImagePath: null,
      createdAt: serverTimestamp(),
      role: 'member',
      accountStatus: 'active',
    })
    await assertSucceeds(batch.commit())
  })

  it('rejects a profile whose reservation is missing from the commit', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'users/member1'), {
        uid: 'member1',
        username: 'Rohan',
        usernameLowercase: 'rohan',
        profileImagePath: null,
        createdAt: serverTimestamp(),
        role: 'member',
        accountStatus: 'active',
      }),
    )
  })

  it("rejects claiming a username reserved by someone else", async () => {
    await seedDoc('usernames/rohan', {
      uid: 'member1',
      usernameLowercase: 'rohan',
      createdAt: Timestamp.now(),
    })
    const db = asUser('member2')
    await assertFails(
      setDoc(doc(db, 'users/member2'), {
        uid: 'member2',
        username: 'Rohan',
        usernameLowercase: 'rohan',
        profileImagePath: null,
        createdAt: serverTimestamp(),
        role: 'member',
        accountStatus: 'active',
      }),
    )
  })

  it('rejects a profile created for another uid', async () => {
    const db = asUser('member1')
    await assertFails(setDoc(doc(db, 'users/member2'), profile('member2', 'Zaid')))
  })

  it('rejects a self-assigned admin role', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'users/member1'), {
        ...profile('member1', 'Rohan'),
        role: 'admin',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects usernames with invalid characters', async () => {
    for (const username of ['ab', 'has space', 'emoji😀', 'a-b-c', 'x'.repeat(21)]) {
      const db = asUser('member1')
      await assertFails(
        setDoc(doc(db, 'users/member1'), {
          ...profile('member1', username),
          usernameLowercase: username.toLowerCase(),
          createdAt: serverTimestamp(),
        }),
      )
    }
  })

  it('rejects reserved usernames', async () => {
    for (const username of ['admin', 'Moderator', 'official', 'chad']) {
      const db = asUser('member1')
      await assertFails(
        setDoc(doc(db, 'users/member1'), {
          ...profile('member1', username),
          usernameLowercase: username.toLowerCase(),
          createdAt: serverTimestamp(),
        }),
      )
    }
  })

  it('rejects documents carrying extra fields such as email', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'users/member1'), {
        ...profile('member1', 'Rohan'),
        email: 'private@example.test',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects a mismatched lowercase username', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'users/member1'), {
        ...profile('member1', 'Rohan'),
        usernameLowercase: 'someone-else',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('lets the owner point at a new profile picture', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertSucceeds(
      updateDoc(doc(asUser('member1'), 'users/member1'), {
        profileImagePath: 'profileImages/member1',
      }),
    )
  })

  it('rejects a username change', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      updateDoc(doc(asUser('member1'), 'users/member1'), {
        username: 'SomeoneElse',
        usernameLowercase: 'someoneelse',
      }),
    )
  })

  it('rejects self-promotion to admin', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      updateDoc(doc(asUser('member1'), 'users/member1'), { role: 'admin' }),
    )
  })

  it('rejects edits from another account', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      updateDoc(doc(asUser('member2'), 'users/member1'), {
        profileImagePath: 'profileImages/member2',
      }),
    )
  })

  it('rejects client-side profile deletion', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(deleteDoc(doc(asUser('member1'), 'users/member1')))
  })
})

describe('usernames', () => {
  it('lets a signed-in user reserve their own username', async () => {
    const db = asUser('member1')
    await assertSucceeds(
      setDoc(doc(db, 'usernames/rohan'), {
        uid: 'member1',
        usernameLowercase: 'rohan',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects reserving a username for someone else', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'usernames/zaid'), {
        uid: 'member2',
        usernameLowercase: 'zaid',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects rewriting an existing reservation', async () => {
    await seedDoc('usernames/rohan', {
      uid: 'member1',
      usernameLowercase: 'rohan',
      createdAt: Timestamp.now(),
    })
    await assertFails(
      setDoc(doc(asUser('member2'), 'usernames/rohan'), {
        uid: 'member2',
        usernameLowercase: 'rohan',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('keeps reservations readable for availability checks', async () => {
    await seedDoc('usernames/rohan', {
      uid: 'member1',
      usernameLowercase: 'rohan',
      createdAt: Timestamp.now(),
    })
    await assertSucceeds(getDoc(doc(asAnon(), 'usernames/rohan')))
  })

  it('rejects reserved or malformed reservations', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'usernames/admin'), {
        uid: 'member1',
        usernameLowercase: 'admin',
        createdAt: serverTimestamp(),
      }),
    )
  })
})

describe('profileImages', () => {
  it('lets the owner upload a compressed avatar', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertSucceeds(
      setDoc(doc(asUser('member1'), 'profileImages/member1'), avatar('member1')),
    )
  })

  it('rejects payloads over the size limit', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      setDoc(
        doc(asUser('member1'), 'profileImages/member1'),
        avatar('member1', { bytes: 49153, data: 'A'.repeat(70000) }),
      ),
    )
  })

  it('rejects encoded strings over the character limit', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      setDoc(
        doc(asUser('member1'), 'profileImages/member1'),
        avatar('member1', { data: 'A'.repeat(70000) }),
      ),
    )
  })

  it('rejects unsupported content types', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      setDoc(
        doc(asUser('member1'), 'profileImages/member1'),
        avatar('member1', { mime: 'image/svg+xml' }),
      ),
    )
  })

  it("rejects writes to another account's avatar", async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('users/member2', profile('member2', 'Zaid'))
    await assertFails(
      setDoc(doc(asUser('member2'), 'profileImages/member1'), avatar('member2')),
    )
  })

  it('rejects a suspended account', async () => {
    await seedDoc(
      'users/member1',
      profile('member1', 'Rohan', { accountStatus: 'suspended' }),
    )
    await assertFails(
      setDoc(doc(asUser('member1'), 'profileImages/member1'), avatar('member1')),
    )
  })

  it('enforces the one-hour update cooldown', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('profileImages/member1', avatar('member1', { updatedAt: Timestamp.now() }))
    await assertFails(
      setDoc(doc(asUser('member1'), 'profileImages/member1'), avatar('member1')),
    )
  })

  it('allows an update after the cooldown has passed', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc(
      'profileImages/member1',
      avatar('member1', {
        updatedAt: Timestamp.fromMillis(Date.now() - 2 * 60 * 60 * 1000),
      }),
    )
    await assertSucceeds(
      setDoc(
        doc(asUser('member1'), 'profileImages/member1'),
        avatar('member1', { data: 'B'.repeat(2048) }),
      ),
    )
  })

  it('lets the owner remove their avatar', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('profileImages/member1', avatar('member1', { updatedAt: Timestamp.now() }))
    await assertSucceeds(deleteDoc(doc(asUser('member1'), 'profileImages/member1')))
  })
})

describe('competitions, submissions and showcases (trusted only)', () => {
  it('lets anyone read confirmed submissions', async () => {
    await seedDoc('submissions/w2026-10-19_member1', submission('member1', 'w2026-10-19'))
    const snapshot = await assertSucceeds(
      getDoc(doc(asAnon(), 'submissions/w2026-10-19_member1')),
    )
    assert.equal(snapshot.data().confirmedScore, 87)
  })

  it('rejects every client write to submissions', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'submissions/w2026-10-19_member1'), submission('member1', 'w2026-10-19')),
    )

    await seedDoc('submissions/w2026-10-19_member1', submission('member1', 'w2026-10-19'))
    await assertFails(
      updateDoc(doc(db, 'submissions/w2026-10-19_member1'), { confirmedScore: 100 }),
    )
    await assertFails(deleteDoc(doc(db, 'submissions/w2026-10-19_member1')))
  })

  it('rejects client writes to competitions', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'competitions/w2026-10-19'), {
        competitionId: 'w2026-10-19',
        startsAt: Timestamp.now(),
        endsAt: Timestamp.now(),
        status: 'active',
        timezone: 'Asia/Kolkata',
      }),
    )
  })

  it('exposes only locked showcases', async () => {
    await seedDoc('showcases/w2026-10-19_member1', {
      uid: 'member1',
      competitionId: 'w2026-10-19',
      slogan: 'Golden hour, golden week.',
      imageId: 'w2026-10-19_member1',
      status: 'locked',
      rank: 3,
      submittedAt: Timestamp.now(),
    })
    await assertSucceeds(getDoc(doc(asAnon(), 'showcases/w2026-10-19_member1')))

    await testEnv.withSecurityRulesDisabled(async (context) => {
      await updateDoc(
        doc(context.firestore(), 'showcases/w2026-10-19_member1'),
        { status: 'removed' },
      )
    })
    await assertFails(getDoc(doc(asAnon(), 'showcases/w2026-10-19_member1')))
  })

  it('rejects client writes to showcases', async () => {
    const db = asUser('member1')
    await assertFails(
      setDoc(doc(db, 'showcases/w2026-10-19_member1'), {
        uid: 'member1',
        competitionId: 'w2026-10-19',
        slogan: 'Self-awarded',
        imageId: 'w2026-10-19_member1',
        status: 'locked',
        rank: 1,
        submittedAt: serverTimestamp(),
      }),
    )
  })

  it('exposes a showcase image only while its showcase is locked', async () => {
    await seedDoc('showcases/w2026-10-19_member1', {
      uid: 'member1',
      competitionId: 'w2026-10-19',
      slogan: 'Golden hour.',
      imageId: 'w2026-10-19_member1',
      status: 'locked',
      rank: 3,
      submittedAt: Timestamp.now(),
    })
    await seedDoc('showcaseImages/w2026-10-19_member1', {
      uid: 'member1',
      competitionId: 'w2026-10-19',
      mime: 'image/webp',
      data: 'A'.repeat(4096),
      bytes: 3000,
      width: 800,
      height: 600,
    })
    await assertSucceeds(getDoc(doc(asAnon(), 'showcaseImages/w2026-10-19_member1')))

    await testEnv.withSecurityRulesDisabled(async (context) => {
      await updateDoc(
        doc(context.firestore(), 'showcases/w2026-10-19_member1'),
        { status: 'removed' },
      )
    })
    await assertFails(getDoc(doc(asAnon(), 'showcaseImages/w2026-10-19_member1')))
    await assertFails(
      setDoc(
        doc(asUser('member1'), 'showcaseImages/w2026-10-19_member1'),
        { uid: 'member1', mime: 'image/webp', data: 'A', bytes: 1, width: 800, height: 600 },
      ),
    )
  })
})

describe('reports, audit and rate limits', () => {
  it('lets a member file one report against another account', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('users/member2', profile('member2', 'Zaid'))
    await assertSucceeds(
      setDoc(doc(asUser('member1'), 'reports/member1_member2'), {
        reporterUid: 'member1',
        reportedUid: 'member2',
        category: 'fake-profile',
        status: 'pending',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects self-reports', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await assertFails(
      setDoc(doc(asUser('member1'), 'reports/member1_member1'), {
        reporterUid: 'member1',
        reportedUid: 'member1',
        category: 'spam',
        status: 'pending',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects forged reporter or report IDs', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('users/member2', profile('member2', 'Zaid'))
    await assertFails(
      setDoc(doc(asUser('member1'), 'reports/member1_member2'), {
        reporterUid: 'member2',
        reportedUid: 'member1',
        category: 'spam',
        status: 'pending',
        createdAt: serverTimestamp(),
      }),
    )
    await assertFails(
      setDoc(doc(asUser('member1'), 'reports/arbitrary-id'), {
        reporterUid: 'member1',
        reportedUid: 'member2',
        category: 'spam',
        status: 'pending',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('rejects unknown report categories', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('users/member2', profile('member2', 'Zaid'))
    await assertFails(
      setDoc(doc(asUser('member1'), 'reports/member1_member2'), {
        reporterUid: 'member1',
        reportedUid: 'member2',
        category: 'free-text-accusation',
        status: 'pending',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('hides reports from members and allows admins', async () => {
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('users/admin1', profile('admin1', 'Aarav_Admin', { role: 'admin' }))
    await seedDoc('reports/member1_member2', {
      reporterUid: 'member1',
      reportedUid: 'member2',
      category: 'spam',
      status: 'pending',
      createdAt: Timestamp.now(),
    })

    await assertFails(getDoc(doc(asUser('member1'), 'reports/member1_member2')))
    await assertSucceeds(getDoc(doc(asUser('admin1'), 'reports/member1_member2')))

    const queue = await assertSucceeds(
      getDocs(
        query(
          collection(asUser('admin1'), 'reports'),
          where('status', '==', 'pending'),
          limit(20),
        ),
      ),
    )
    assert.equal(queue.size, 1)
  })

  it('lets an admin resolve a report but not rewrite it', async () => {
    await seedDoc('users/admin1', profile('admin1', 'Aarav_Admin', { role: 'admin' }))
    await seedDoc('reports/member1_member2', {
      reporterUid: 'member1',
      reportedUid: 'member2',
      category: 'spam',
      status: 'pending',
      createdAt: Timestamp.now(),
    })

    await assertSucceeds(
      updateDoc(doc(asUser('admin1'), 'reports/member1_member2'), { status: 'dismissed' }),
    )
    await assertFails(
      updateDoc(doc(asUser('admin1'), 'reports/member1_member2'), {
        status: 'pending',
        reportedUid: 'someone-else',
      }),
    )
    await assertFails(
      updateDoc(doc(asUser('member1'), 'reports/member1_member2'), { status: 'dismissed' }),
    )
  })

  it('treats a suspended admin as a non-admin', async () => {
    await seedDoc(
      'users/admin1',
      profile('admin1', 'Aarav_Admin', { role: 'admin', accountStatus: 'suspended' }),
    )
    await seedDoc('reports/member1_member2', {
      reporterUid: 'member1',
      reportedUid: 'member2',
      category: 'spam',
      status: 'pending',
      createdAt: Timestamp.now(),
    })
    await assertFails(getDoc(doc(asUser('admin1'), 'reports/member1_member2')))
  })

  it('keeps the audit trail admin-readable and write-denied', async () => {
    await seedDoc('users/admin1', profile('admin1', 'Aarav_Admin', { role: 'admin' }))
    await seedDoc('users/member1', profile('member1', 'Rohan'))
    await seedDoc('adminAudit/event1', {
      actionType: 'score-correction',
      actorUid: 'admin1',
      targetUid: 'member1',
      reason: 'Verified duplicate entry.',
      createdAt: Timestamp.now(),
    })

    await assertSucceeds(getDoc(doc(asUser('admin1'), 'adminAudit/event1')))
    await assertFails(getDoc(doc(asUser('member1'), 'adminAudit/event1')))
    await assertFails(
      setDoc(doc(asUser('admin1'), 'adminAudit/event2'), {
        actionType: 'score-correction',
        actorUid: 'admin1',
        targetUid: 'member1',
        reason: 'Forged.',
        createdAt: serverTimestamp(),
      }),
    )
  })

  it('keeps rate-limit counters inaccessible', async () => {
    await seedDoc('rateLimits/member1', { windowStart: Timestamp.now(), count: 3 })
    await assertFails(getDoc(doc(asUser('member1'), 'rateLimits/member1')))
    await assertFails(
      setDoc(doc(asUser('member1'), 'rateLimits/member1'), { count: 0 }),
    )
  })
})

describe('default deny', () => {
  it('rejects unknown collections', async () => {
    const db = asUser('member1')
    await assertFails(setDoc(doc(db, 'privateNotes/note1'), { text: 'nope' }))
    await assertFails(getDoc(doc(db, 'privateNotes/note1')))
  })

  it('rejects anonymous writes everywhere', async () => {
    const db = asAnon()
    await assertFails(
      setDoc(doc(db, 'users/member1'), {
        ...profile('member1', 'Rohan'),
        createdAt: serverTimestamp(),
      }),
    )
    await assertFails(setDoc(doc(db, 'submissions/w2026-10-19_member1'), { score: 1 }))
    await assertFails(setDoc(doc(db, 'adminAudit/x'), { actionType: 'x' }))
  })
})
