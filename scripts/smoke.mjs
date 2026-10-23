/**
 * Local verification script (not shipped to production).
 *
 * 1. Exercises the demo service layer: ranking order, confirmation, locks,
 *    showcase eligibility, admin authorization and audit records.
 * 2. Server-renders every public route to catch render-time crashes.
 *
 * Run with: node scripts/smoke.mjs
 */
import { createServer } from 'vite'
import assert from 'node:assert/strict'

const vite = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
})

let failures = 0
const check = (name, fn) => {
  try {
    fn()
    console.log(`  PASS  ${name}`)
  } catch (error) {
    failures += 1
    console.error(`  FAIL  ${name}`)
    console.error(error)
  }
}

try {
  const { demoStore } = await vite.ssrLoadModule('/src/services/demo/demoStore.ts')
  const { compareSubmissions } = await vite.ssrLoadModule('/src/utils/ranking.ts')

  console.log('\nRanking')
  const board = demoStore.getLeaderboard()
  check('has at least 100 confirmed participants', () => {
    assert.ok(board.totalParticipants >= 120, `got ${board.totalParticipants}`)
  })
  check('Top 100 is capped', () => assert.equal(board.ranked.length, 100))
  check('directory holds the remainder', () => {
    assert.equal(board.directory.length, board.totalParticipants - 100)
  })
  check('scores descend', () => {
    for (let i = 1; i < board.ranked.length; i += 1) {
      assert.ok(board.ranked[i - 1].score >= board.ranked[i].score)
    }
  })
  check('rank 1 is TRUE ADAM', () => assert.equal(board.ranked[0].title, 'TRUE ADAM'))
  check('ranks 2-3 are ELITE CHAD', () => {
    assert.equal(board.ranked[1].title, 'ELITE CHAD')
    assert.equal(board.ranked[2].title, 'ELITE CHAD')
  })
  check('rank 10 is TOP 10', () => assert.equal(board.ranked[9].title, 'TOP 10'))
  check('rank 11 is RANKED', () => assert.equal(board.ranked[10].title, 'RANKED'))
  check('suspended account is excluded from the board', () => {
    assert.ok(!board.ranked.some((entry) => entry.username === 'RohitOfficial'))
  })
  check('tie-breaker is deterministic', () => {
    const copy = [...board.ranked]
      .reverse()
      .map((entry) => ({
        uid: entry.uid,
        username: entry.username,
        profileImagePath: entry.profileImagePath,
        score: entry.score,
        submittedAt: entry.submittedAt,
      }))
      .sort(compareSubmissions)
    copy.forEach((entry, index) => {
      assert.equal(entry.username, board.ranked[index].username)
    })
  })

  console.log('\nAuthentication')
  assert.throws(() => demoStore.signIn({ identifier: 'Challenger', password: 'wrong' }))
  const challenger = demoStore.signIn({
    identifier: 'Challenger',
    password: demoStore.demoPassword,
  })
  check('valid demo sign-in', () => assert.equal(challenger.username, 'Challenger'))
  check('username availability is case-insensitive', () => {
    assert.equal(demoStore.isUsernameAvailable('challenger'), false)
    assert.equal(demoStore.isUsernameAvailable('A_New_Name'), true)
  })
  check('duplicate signup is rejected', () => {
    assert.throws(() =>
      demoStore.signUp({
        username: 'cHaLLenger',
        email: 'new@example.com',
        password: 'Strong1234',
      }),
    )
  })

  console.log('\nWeekly submission')
  const before = demoStore.getWeeklyStatus(challenger.uid)
  check('new account starts unranked and can submit', () => {
    assert.equal(before.canSubmit, true)
    assert.equal(before.rank, null)
  })
  const boardsBefore = demoStore.getLeaderboard()
  const confirm = await demoStore.confirmSubmission({
    competitionId: boardsBefore.competition.id,
    score: 95,
    scoringVersion: 'test',
    analyzedAt: new Date().toISOString(),
  })
  check('confirmation returns a derived rank and eligibility', () => {
    assert.ok(confirm.rank >= 1)
    assert.equal(confirm.showcaseEligible, confirm.rank <= 10)
  })
  check('score is locked after confirmation', () => {
    const after = demoStore.getWeeklyStatus(challenger.uid)
    assert.equal(after.canSubmit, false)
    assert.equal(after.submission.confirmedScore, 95)
  })
  let duplicateBlocked = false
  try {
    await demoStore.confirmSubmission({
      competitionId: boardsBefore.competition.id,
      score: 100,
      scoringVersion: 'test',
      analyzedAt: new Date().toISOString(),
    })
  } catch (error) {
    duplicateBlocked = error.code === 'already-confirmed'
  }
  check('duplicate confirmation is blocked', () => assert.equal(duplicateBlocked, true))

  console.log('\nTop 10 showcase')
  const eligibility = demoStore.getShowcaseEligibility()
  check('confirmed top-10 account is eligible', () => assert.equal(eligibility.eligible, true))
  await demoStore.submitShowcase({ slogan: 'Test slogan', imageFile: null })
  const locked = demoStore.getShowcaseEligibility()
  check('showcase locks after submission', () => assert.equal(locked.showcase.locked, true))
  let lockBlocked = false
  try {
    await demoStore.submitShowcase({ slogan: 'Second slogan', imageFile: null })
  } catch (error) {
    lockBlocked = error.code === 'showcase-locked'
  }
  check('second submission is rejected', () => assert.equal(lockBlocked, true))
  const publicProfile = demoStore.getPublicProfile('Challenger')
  check('public profile exposes the eligible showcase', () => {
    assert.equal(publicProfile.showcase.slogan, 'Test slogan')
    assert.ok(publicProfile.rank <= 10)
  })

  console.log('\nAdmin authorization')
  demoStore.signOut()
  demoStore.signIn({ identifier: 'Zaid', password: demoStore.demoPassword })
  let forbidden = false
  try {
    demoStore.getAdminOverview()
  } catch (error) {
    forbidden = error.code === 'forbidden'
  }
  check('non-admin cannot read admin overview', () => assert.equal(forbidden, true))

  demoStore.signOut()
  const admin = demoStore.signIn({
    identifier: 'Aarav_Admin',
    password: demoStore.demoPassword,
  })
  check('admin session starts', () => assert.equal(admin.role, 'admin'))
  const overview = demoStore.getAdminOverview()
  check('admin overview contains real counts', () => {
    assert.equal(overview.stats.totalUsers, demoStore.listUsers().length)
  })
  const target = demoStore.listUsers('Challenger')[0]
  demoStore.correctScore(target.uid, 40, 'Smoke test correction.')
  const corrected = demoStore
    .getLeaderboard()
    .ranked.find((entry) => entry.uid === target.uid)
  check('score correction recalculates rank', () => {
    if (corrected) assert.equal(corrected.score, 40)
    else {
      const directory = demoStore
        .getLeaderboard()
        .directory.find((entry) => entry.uid === target.uid)
      assert.ok(directory)
      assert.ok(directory.rank > 100)
    }
  })
  const loseEligibility = demoStore.getPublicProfile('Challenger')
  check('showcase is hidden after falling out of the Top 10', () => {
    assert.equal(loseEligibility.showcase, null)
  })
  console.log('    pending IDs:', overview.pendingReports.map((report) => report.id))
  assert.ok(overview.pendingReports.length > 0)
  demoStore.resolveReport(overview.pendingReports[0].id, 'dismissed')
  const audit = demoStore.getAuditEvents()
  check('audit records the correction and report decision', () => {
    assert.ok(audit.some((event) => event.actionType === 'score-correction'))
    assert.ok(audit.some((event) => event.actionType === 'report-dismissed'))
  })
  check('auditing a reason is enforced', () => {
    assert.throws(() => demoStore.correctScore(target.uid, 50, '  '))
  })
  check('admin cannot suspend itself', () => {
    let code = null
    try {
      demoStore.suspendUser(admin.uid, 'Self test')
    } catch (error) {
      code = error.code
    }
    assert.equal(code, 'forbidden')
  })

  console.log('\nRender smoke test')
  const React = await import('react')
  const { renderToString } = await import('react-dom/server')
  const { StaticRouter } = await import('react-router-dom')
  const { App } = await vite.ssrLoadModule('/src/App.tsx')
  const { AuthProvider } = await vite.ssrLoadModule('/src/hooks/useAuth.tsx')
  const { ToastProvider } = await vite.ssrLoadModule('/src/hooks/useToast.tsx')
  const { SubmissionDraftProvider } = await vite.ssrLoadModule(
    '/src/hooks/useSubmissionDraft.tsx',
  )

  const renderRoute = (path) => {
    const element = React.createElement(
      StaticRouter,
      { location: path },
      React.createElement(
        AuthProvider,
        null,
        React.createElement(
          ToastProvider,
          null,
          React.createElement(
            SubmissionDraftProvider,
            null,
            React.createElement(App, null),
          ),
        ),
      ),
    )
    return renderToString(element)
  }

  for (const path of [
    '/',
    '/login',
    '/signup',
    '/forgot-password',
    '/leaderboard',
    '/participants',
    '/rules',
    '/profile/Zaid',
    '/dashboard',
    '/submit',
    '/showcase',
    '/admin',
    '/missing-page',
  ]) {
    check(`renders ${path}`, () => {
      const html = renderRoute(path)
      assert.ok(html.length > 500, `unexpectedly short HTML for ${path}`)
    })
  }
} finally {
  await vite.close()
}

if (failures > 0) {
  console.error(`\n${failures} check(s) failed.`)
  process.exit(1)
}
console.log('\nAll checks passed.')
