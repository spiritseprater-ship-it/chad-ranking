# CHAD RANKING

> **THE RANKING IS YOURS TO CLAIM.**
> Enter. Compete. Claim your rank.

A premium, classic weekly community ranking competition for a small group of
friends. Three photos, one provisional entertainment score, one confirmed rank,
a live weekly leaderboard, and an exclusive Top 10 showcase.

**Current status: Phase 1 — complete, responsive frontend with a labelled demo
layer.** Authentication, cloud persistence, uploads, trusted score confirmation,
moderation and the scheduled weekly reset are **not connected to a backend yet**.
Nothing in this repository claims that they are.

**Documentation**

- [`docs/FIREBASE_PLAN.md`](docs/FIREBASE_PLAN.md) — Phase 2 architecture, data
  model, trusted operations, reset design, security rules strategy.
- [`docs/FREE_TIER.md`](docs/FREE_TIER.md) — verified quotas and the Spark/Blaze
  decision the owner must make.
- [`docs/SCORING.md`](docs/SCORING.md) — the exact entertainment-score formula.
- [`docs/TESTING.md`](docs/TESTING.md) — what was verified, what was not.

---

## 1. What actually works today

| Area | Phase 1 status |
| --- | --- |
| Responsive landing page, navigation, footer | ✅ Built |
| Sign-up / login / recovery UI + validation | ✅ Built (demo sign-in only) |
| Dashboard, submission, result and confirmation screens | ✅ Built |
| Live camera capture + three-photo workflow | ✅ Built (`getUserMedia`, upload fallback) |
| Local image analysis and documented scoring heuristic | ✅ Working in the browser |
| Leaderboard, Top 100, participant directory, tie-breakers | ✅ Built against the service contract |
| Top 10 titles, TRUE ADAM, showcase UI and locking rules | ✅ Built |
| Admin dashboard, user management, moderation queue, audit UI | ✅ Built (demo service) |
| Loading / empty / error / access-denied states | ✅ Built |
| Firebase projects, Auth, Firestore, Storage | ⛔ Phase 2 |
| Permanent profile-picture upload | ⛔ Phase 2 (placeholder avatar shown) |
| Trusted server-side score confirmation and rank calculation | ⛔ Phase 2 |
| Scheduled weekly reset | ⛔ Phase 2 |
| Deployed GitHub Pages site | ⚠️ Workflow included; Pages must be enabled by the owner |
| Firestore / Storage Security Rules | ⚠️ Drafts included, **not deployed or tested** |

### Demo mode (for reviewing the UI)

When Firebase is **not** configured and `VITE_ENABLE_DEMO_PREVIEW=true`, the app
uses a clearly labelled in-memory demo backend. It exists only so every screen
can be exercised end to end. It is not authentication and it is not a leaderboard:
state resets when the tab reloads.

Demo accounts (password `ChadDemo123`):

| Username | Role | What it demonstrates |
| --- | --- | --- |
| `Challenger` | member, unranked | full photo → provisional → confirm flow |
| `Zaid` | member, Top 10 | locked showcase + Top 10 profile |
| `Aarav_Admin` | administrator | admin overview, corrections, moderation, audit |

The demo password is public by design and only exists to review the interface.
It has nothing to do with the eventual Firebase Authentication setup.

---

## 2. Stack

- React 19 + TypeScript (strict) + Vite 8
- Tailwind CSS 4 with a token-based design system
- React Router 7
- Lucide icons
- Self-hosted variable fonts (Inter, Manrope, Newsreader) via Fontsource
- Firebase Authentication + Cloud Firestore in Phase 2 (client SDK prepared)
- GitHub Pages + GitHub Actions for hosting (frontend)

No Supabase. No paid AI API. The provisional score is a documented local
heuristic, not an AI model.

---

## 3. Quick start

Requirements: **Node.js 22.12+** (tested with 22.22) and npm 10+.

```bash
git clone https://github.com/<your-account>/chad-ranking.git
cd chad-ranking
npm install
```

### Preview the interface with sample data

```bash
cp .env.example .env.local
# then set:
# VITE_ENABLE_DEMO_PREVIEW=true
npm run dev
```

Open <http://localhost:5173>. Without any configuration the app still renders,
but data pages show “backend not configured” states instead of pretending to
work.

### Production build

```bash
npm run build      # tsc -b && vite build → dist/
npm run preview    # serves the production build locally
```

### Automated checks

```bash
npm run smoke      # service-layer + server-render checks (no browser needed)
npm run ci         # production build + smoke checks
```

`scripts/smoke.mjs` verifies ranking order and tie-breakers, demo auth rules,
submission locking, duplicate confirmation rejection, Top 10/showcase locking,
admin authorization, audit recording, and that every route server-renders.
It does **not** replace a real browser test — see
[`docs/TESTING.md`](docs/TESTING.md).

---

## 4. Environment variables

Copy `.env.example` → `.env.local` (git-ignored). All values are public web
configuration except the things that must never exist in a frontend at all.

| Variable | Purpose |
| --- | --- |
| `VITE_FIREBASE_API_KEY` | Firebase web config (public) |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase web config (public) |
| `VITE_FIREBASE_PROJECT_ID` | Firebase web config (public) |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase web config (public, optional in Phase 1) |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase web config (public) |
| `VITE_FIREBASE_APP_ID` | Firebase web config (public) |
| `VITE_BASE_PATH` | Override the GitHub Pages base path (e.g. `/` for a custom domain) |
| `VITE_ENABLE_DEMO_PREVIEW` | `true` only for interface review; ignored when Firebase is configured |

> **Firebase web configuration is public, not a secret.** Anyone can read it from
> the bundle. It is safe only together with Firestore/Storage Security Rules and
> trusted server-side validation. **Never** put a service-account JSON, private
> key, admin password or `.env` file with secrets in this repository or in any
> `VITE_*` variable.

Demo mode is selected with an explicit precedence:

1. Firebase configured → Firebase service layer (**Phase 2 placeholder today**)
2. otherwise demo flag `true` → labelled sample backend
3. otherwise → every protected action fails with a setup message

A production build never silently falls back to sample data.

---

## 5. Project structure

```text
src/
  components/
    admin/         AdminStatCard, ModerationTable, UserManageDialog
    auth/          AuthShell, guards, demo account panel
    common/        banners, countdown, rank badges, leaderboard rows, error boundary
    home/          landing-page sections
    layout/        navbar, footer, wordmark
    profile/       showcase card, report dialog
    score/         score card / breakdown / disclaimer
    submission/    camera, photo slots, steps, rank-title note
    ui/            buttons, forms, avatars, badges, notices, modal, states
  config/          env, constants
  firebase/        client initialisation (Phase 2; lazy SDK imports)
  hooks/           auth, async loading, countdown, toasts, draft, debounce, titles
  layouts/         root + admin layouts
  pages/           every route
  services/        contracts, errors, demo store, firebase placeholders, scoring
  styles/          Tailwind tokens + base styles
  types/           domain + service contracts
  utils/           cn, datetime (IST), ranking, validation
public/            favicon, SPA 404 fallback, robots.txt, .nojekyll
scripts/           smoke checks
docs/              Phase 2 plan, free-tier notes, scoring, testing
firestore.rules    DRAFT rules (not deployed)
storage.rules      DRAFT rules (not deployed)
```

UI components do not import the demo store; pages talk only to the service
interfaces in `src/types/services.ts`. Phase 2 replaces the implementations, not
the screens.

### Useful implementation details

- **Weekly windows** are derived from Asia/Kolkata Monday 00:00 and have an
  explicit ID (`wYYYY-MM-DD`). Countdowns use the backend-provided `endsAt`.
- **Ranking** is a pure function: score desc → earlier `submittedAt` → stable
  `uid`. Ranks are always derived, never stored as a client value.
- **Photos** live only in browser memory. The draft context stores the
  provisional score, never the images. Object URLs are revoked on replace,
  analysis, clear and unmount.
- **GitHub Pages routing** uses `public/404.html` + an inline restore script in
  `index.html`; deep links survive refresh at `/repository-name/...`.

---

## 6. Deploy the frontend to GitHub Pages

The workflow `.github/workflows/deploy.yml` builds and publishes `dist/` on every
push to `main`.

1. Push the repository to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Ensure the default branch is `main` (or edit the workflow trigger).
4. Add public Firebase web values under **Settings → Secrets and variables →
   Actions → Variables** if/when Phase 2 is configured.
5. Run the **Deploy to GitHub Pages** workflow (or push to `main`).
6. Open `https://<user>.github.io/<repo>/`.

The Vite config automatically sets `base` to `/<repository>/` on GitHub Actions,
and the build injects that same path into `public/404.html`, so deep links work
on project sites and after a repository rename without edits. For a custom domain,
add a `public/CNAME` file and set the repository variable `VITE_BASE_PATH=/`; the
fallback page is updated automatically. For a user site at the domain root, set
`VITE_BASE_PATH=/` as well.

The deployment is **not performed by this change**. Enabling Pages is an owner
action.

---

## 7. Phase 2 — backend decisions before writing code

Read [`docs/FIREBASE_PLAN.md`](docs/FIREBASE_PLAN.md) in full. The short version:

- Authentication: Firebase Email/Password. Login accepts username or email in the
  UI; the final username-resolution approach is an open decision (see below).
- Data: Firestore with public profile fields, submissions, showcases, reports,
  audit, competitions. No email addresses in public documents.
- **Score confirmation, rank calculation, showcase eligibility, admin actions
  and weekly reset must run in a trusted environment.** Browser values are never
  trusted.
- Current free-tier facts (verified 23 October 2026) create a real architectural
  choice:
  - **Cloud Functions and Cloud Storage are not available on the Spark plan.**
    Cloud Storage has required Blaze since 3 February 2026; Functions requires
    Blaze to deploy. Firestore and Email/Password Auth remain free within quotas.
  - **Option A — Blaze, stay inside free quotas:** Cloud Functions + Storage,
    card on file, budget alerts, explicit owner approval. Simplest and fully
    aligned with this specification.
  - **Option B — strictly ₹0:** Spark Auth + Firestore, with a free external
    serverless backend holding a service account for trusted confirmations,
    moderation and reset; images stored as compressed Firestore data (or another
    explicitly approved free store).
  - **Option C — rules-only browser confirmation:** rejected. It allows clients
    to choose scores and cannot satisfy the security requirements.

Do not enable billing, deploy rules, or call the backend “secure” until the owner
chooses an option and the behaviour has been tested in the Firebase Emulator
Suite. `firestore.rules` and `storage.rules` are **drafts**.

### Username sign-in decision

Firebase Email/Password requires an email credential. A strictly free,
server-verified username-only sign-in is not possible without either a trusted
function/back end or a synthetic-email design with owner-assisted recovery:

- **Recommended for Spark:** sign in with email + password; the public identity
  remains the unique username. The Phase 1 form already accepts either.
- **If username-only login is required:** Option A with a callable resolution
  function, or a documented synthetic-email scheme with an explicit recovery
  process. Choose this before Phase 2 authentication is implemented.

### First administrator

Performed through a trusted process, never through the UI:

1. Create the owner account (app or Firebase Console).
2. In the Firebase Console, set `users/{uid}.role = "admin"` (console writes are
   trusted), or run a one-off Admin SDK script locally with a service account
   that is **not committed**.
3. Sign out and back in. The admin UI shows an access-denied screen to everyone
   else; every protected backend action re-checks the role.
4. Grant or revoke further admins the same way. Never ship an admin password or
   a service-account key with the site.

### Weekly reset (planned)

- Server-side, idempotent, derived from explicit IST competition timestamps.
- Free scheduling option: a GitHub Actions scheduled workflow
  (`30 18 * * 0` UTC = Monday 00:00 IST) using a service-account secret, plus
  manual dispatch. GitHub schedules can be delayed and are disabled after
  prolonged repository inactivity; therefore expiry is *also* enforced from
  timestamps at submission time. A late reset never allows entries into the old
  week.
- Option A alternative: a scheduled Cloud Function (Blaze).
- Cleanup: previous showcases are hidden immediately when eligibility ends and
  their stored files/records are deleted by the trusted cleanup job. No archive.

---

## 8. Security notes

- No secrets live in this repository. `.env*` except `.env.example` is ignored.
- Service-account files and private keys are explicitly ignored by `.gitignore`.
- Client-side role, score and rank values are never trusted. The demo layer
  enforces roles only to demonstrate UI states; it is not a security boundary.
- The Phase 1 demo stores its session in `sessionStorage` under an explicitly
  demo-only key. Production authentication will use Firebase sessions; neither
  uses `localStorage` as an authority for accounts or ranks.
- Firestore/Storage rules must prevent self-granted roles, self-set scores,
  cross-account edits, showcase uploads while ineligible, and reads of private
  moderation data. Drafts are included; **test them before real data exists.**
- Raw scoring photos are never uploaded, and clearing browser memory is described
  honestly in the Privacy page — it is not a guarantee of erasing every
  device-level trace.

---

## 9. Free-tier summary

See [`docs/FREE_TIER.md`](docs/FREE_TIER.md) for the verified table and links.
Highlights:

- Firestore Spark: 1 GiB stored, 50k reads/day, 20k writes/day, 20k deletes/day.
- Email/Password Authentication: no-cost for a community of this size.
- Cloud Functions: **Blaze only** (2M invocations/month free allowance on Blaze).
- Cloud Storage: **Blaze only since 3 Feb 2026**.
- GitHub Pages / Actions: free for public repositories; static hosting only;
  scheduled jobs may be delayed.
- Quotas can change. Graceful quota errors are part of the Phase 2 work.

Never enable a paid billing plan without the owner's explicit authorization.

---

## 10. Known limitations in this phase

- No real accounts, sessions, sharing or persistence; demo state resets on reload.
- No profile-picture or showcase-photo upload; designed placeholders are shown.
- Score confirmation writes to the demo store only. It is not official.
- Camera capture requires HTTPS (GitHub Pages/localhost are secure). Physical
  camera behaviour still needs device testing.
- Password recovery, account deletion and report throttling are described in the
  UI but depend on Phase 2 infrastructure.
- Firestore indexes and rules are drafts.
- Visual verification at 360/390/768/1024/1440 px and real assistive-technology
  testing should be repeated by a human before launch; the environment used to
  build Phase 1 had no browser automation.

---

## 11. Roadmap

1. ✅ Phase 1 — design system, routes, pages, demo service layer, camera/local
   scoring, admin/moderation UI, GitHub Pages configuration.
2. ⏳ Phase 2 — choose backend architecture; Firebase Auth; profiles and username
   reservation; persistent leaderboard.
3. ⏳ Phase 3 — trusted confirmation, ranking, Top 10 lifecycle and image cleanup.
4. ⏳ Phase 4 — moderation persistence, scheduled reset, rules tests, live
   deployment and device testing.

See [`docs/FIREBASE_PLAN.md`](docs/FIREBASE_PLAN.md) for milestones and
[`docs/TESTING.md`](docs/TESTING.md) for the verified/unverified matrix.

---

## 12. Credits

Fonts: Inter, Manrope and Newsreader (SIL Open Font License) via Fontsource.
Icons: Lucide (ISC). Rating labels are fictional and used for entertainment only.
