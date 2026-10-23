# Phase 2 — Firebase & trusted backend plan

> **Status update (October 2026):** the architecture is decided and approved —
> **Spark + Cloudflare Workers Free**, no Blaze, no Functions, no Storage.
> Step 1 (rules, schema, indexes, emulator tests) is implemented; see
> [`PHASE2_SCHEMA.md`](PHASE2_SCHEMA.md) for the authoritative schema and trust
> boundary. Sections below that describe choosing between Blaze and a free
> backend are retained as background; where they conflict with
> `PHASE2_SCHEMA.md`, the schema document wins.

Status: **planning document**. Nothing described here is deployed. The Phase 1
service layer is deliberately shaped so these implementations replace the demo
ones without changing the pages.

Read [`FREE_TIER.md`](FREE_TIER.md) first; the free-plan constraints drive the
architecture.

---

## 1. Non-negotiable requirements

1. Public leaderboard data is shared and authoritative, never `localStorage`.
2. A client can never set its own score, rank, role, showcase eligibility or
   moderation state.
3. Score confirmation validates the **active competition**, the account, the
   one-entry lock **and the score derivation** before writing.
4. Rank is derived from authoritative data after the write.
5. Weekly reset is idempotent, server-side, schedule-independent of visitors and
   works even if the scheduler runs late.
6. Showcase content is deleted when eligibility ends or the week resets.
7. Admin actions require a server-checked admin role and produce a minimal audit
   record.
8. Raw scoring photos are not permanently retained.
9. No service-account key in the frontend or repository.
10. No paid service is silently required.

---

## 2. Approved decision (October 2026)

- **Plan:** Firebase **Spark** only. No billing account, no payment method, no
  Cloud Functions, no Firebase Cloud Storage.
- **Trusted backend:** a **Cloudflare Worker on the free plan** (100,000
  requests/day, 10 ms CPU per request, 5 cron triggers) holding a
  Firestore-scoped service account. The key lives only in Cloudflare.
- **Images:** compressed WebP stored as bounded Firestore documents.
- **Reset:** competition IDs derived from Monday 00:00 IST; a Worker cron performs
  cleanup. No client may request or delay a reset.
- **Rejected:** rules-only browser confirmation (clients would choose scores),
  Blaze/Functions/Storage, R2 (payment method), Deno Deploy (shutdown announced),
  Supabase.

The implemented collection schema, ID formats, rules invariants and test
coverage are specified in [`PHASE2_SCHEMA.md`](PHASE2_SCHEMA.md).

## 3. Authentication

- Provider: Firebase **Email/Password**. No phone/SMS (billed), no social login
  unless requested.
- Sign-up collects username, private email, password. Email is stored only by
  Firebase Auth — not in Firestore public documents.
- Username reservation: a transaction creates `usernames/{usernameLower}` and
  `users/{uid}` together. Document ID uniqueness enforces case-insensitive
  uniqueness; rules restrict creation to the signed-in UID and deny updates.
  Reserved/impersonation-sensitive names are blocked in both client validation
  and rules/back end.
- Rate-limit sign-up attempts at the provider and via App Check if practical.
- Password recovery: Firebase reset email. Show a privacy-safe “if an account
  exists” message.
- **Username vs email sign-in:** see README §7. Recommended for Spark: email +
  password sign-in, public username. If username-only sign-in is mandatory,
  Option A with a resolution callable or a documented synthetic-email design
  with owner-assisted recovery. Decide before writing the auth service.
- Duplicate username errors must be surfaced as field errors, not raw Firebase
  codes.

### Admin role

- `users/{uid}.role` is `member` or `admin`, immutable from the client.
- The first admin is set in the Firebase Console or via a local Admin SDK script.
- Every protected backend call re-reads the role from Firestore; the frontend UI
  gate is cosmetic only.
- Grant/revoke is allowed only to an existing admin through a trusted operation;
  the action is audited.

---

## 4. Data model

All timestamps are Firestore `Timestamp` values written by the server. Public
read models are denormalised only where it avoids extra reads.

### `users/{uid}` — public

```text
uid, username, usernameLowercase, profileImagePath,
createdAt, role, accountStatus
```

No email, password, notes or private tokens. `role` and `accountStatus` are
server-controlled.

### `usernames/{usernameLowercase}`

```text
uid, createdAt
```

Unique reservation; created atomically with the user document.

### `competitions/{competitionId}`

```text
competitionId ("w2026-10-19"), weekLabel,
startsAt, endsAt, status ("active" | "closed"), timezone ("Asia/Kolkata")
```

Only the current competition (and briefly the closing one) is retained. No
historical leaderboard.

### `meta/activeCompetition` (optional pointer)

```text
competitionId, endsAt, updatedAt
```

Public read, backend write. Clients may display state from it but must never use
it to authorize a write.

### `submissions/{competitionId}_{uid}`

```text
uid, competitionId, confirmedScore, submittedAt,
submissionStatus ("confirmed"), scoringVersion,
moderationStatus ("clear" | "under_review" | "disqualified")
```

Fixed document ID gives one submission per user per week. Draft/provisional
state is never written. Rank is not stored on the submission; it is derived by
the leaderboard query (score desc, submittedAt asc, uid asc) and can be
recomputed at any time.

### `showcases/{competitionId}_{uid}`

```text
uid, competitionId, slogan, imagePath, submittedAt,
status ("locked" | "removed" | "cleanup_pending"), cleanupAttempts
```

One active showcase per eligible user per competition. Public read only while
`status == "locked"` and the user is in the current Top 10 (checked by the
backend/leaderboard read path). Records for previous weeks are deleted.

### `reports/{reportId}`

```text
reporterUid, reportedUid, category, status, createdAt
```

Private to admins. No screenshots, accusations or free-form private details.
Duplicate/report-rate protection in the backend.

### `adminAudit/{eventId}`

```text
actionType, actorUid, targetUid, reason, createdAt
```

No images, emails, snapshots or previous scores beyond what is necessary. Short
documented retention period (e.g. 90 days) enforced by cleanup.

### `adminStatus/{uid}` (optional)

Private flags or support notes; never public. Prefer keeping this empty unless a
real operational need appears.

### Deleted / never created

- Raw photos and photo history
- Previous leaderboards or winner archives
- Raw analysis metrics tied to a person
- Public email collections
- Duplicated profile data across many collections

---

## 5. Trusted operations

| Operation | Client | Trusted backend |
| --- | --- | --- |
| Create account + reserve username | transaction | rules validate shape/UID |
| Upload profile picture | direct upload to owner path | size/content-type rules; optional backend validation |
| Submit provisional score | browser only | — (never persisted) |
| Confirm score | request with temporary image evidence | validate competition window, active account, lock, rate limit; recompute score; write submission; derive rank |
| Read leaderboard | query confirmed submissions | rules expose only public fields |
| Top 10 showcase submit | request | re-check rank ≤ 10, slogan length, image; lock record; upload permanent image through backend |
| Eligibility loss | event or scheduled pass | hide immediately, delete image, mark/remove showcase |
| Admin actions | request | re-check admin role; validate bounds; apply; audit |
| Weekly reset | scheduler | idempotent close/create/cleanup; audit |

### How to verify a photo-derived score

The score depends on pixels. A server cannot trust pixels or metrics sent by a
browser. The genuine options are:

1. **Temporary transfer + server re-analysis (recommended):** send the three
   compressed photos (e.g. 1080px, ≤1 MB each) to the trusted function/endpoint
   over HTTPS; it decodes them with an image library (e.g. `sharp` or pure-JS
   decoders), recomputes the exact documented formula, and responds with the
   confirmed score and rank. The images are processed in memory, never written to
   permanent storage, and the request payload is logged without image data.
2. **Weaker, documented limitation:** if the chosen free host cannot decode
   images, the server can enforce lock, eligibility, bounds and rate limits but
   cannot verify the derivation. That does **not** meet requirement 3 above and
   must not be presented as secure confirmation.

The local Phase 1 score remains provisional. Do not copy the client score into a
“confirmed” record without server re-analysis.

---

## 6. Weekly reset design

- Week = Monday 00:00 IST → next Monday 00:00 IST. ID: `wYYYY-MM-DD`.
- Reset routine receives a target competition ID and the trusted clock:
  1. transactionally close the old competition if its `endsAt` has passed;
  2. create/activate the next competition (same doc if it already exists);
  3. delete previous-week submissions and showcase records (or mark
     `cleanup_pending` with attempts if a delete fails);
  4. delete stored showcase images and transient scoring images;
  5. clear showcase locks by deleting their records;
  6. remove slogans with the records;
  7. preserve users, usernames, profile pictures, roles and audit;
  8. write one audit event with the result and counts (no participant data).
- **Idempotency:** re-running with the same target produces the same state; use
  transactions and conditional deletes. Running twice must not delete the new
  week's entries.
- **Late scheduler:** submission confirmation checks `now < endsAt` from a
  trusted clock. If the scheduler is late, the old competition is expired for
  writes, and the UI shows “week closed”; the reset routine catches up when it
  runs. No user visit is required for cleanup, and a browser timer is never the
  authority.
- **Scheduling options:**
  - Blaze: scheduled Cloud Function (or Cloud Scheduler → HTTPS function).
  - Spark: GitHub Actions cron `30 18 * * 0` UTC plus manual dispatch, using a
    short-lived service-account credential stored as an Actions secret and
    calling the reset endpoint. GitHub schedules can be delayed and are disabled
    after 60 days of repository inactivity; documented contingency is a manual
    dispatch. Option B provider cron is an alternative.
- **Cleanup failures:** never expose a pending-deletion image. Public queries
  exclude it immediately; retry with backoff; record only an operational status
  (not user content). If repeated failures occur, alert the owner.

---

## 7. Images and storage

Strictly temporary:

- scoring photos exist in memory, are sent for verification, and are discarded;
- no image history, no thumbnails, no “previous attempts”.

Permanent:

- profile picture: target 512×512, JPEG/WebP, ≤1 MB pre-compression, compressed
  and metadata-stripped client-side before upload; path tied to UID;
- showcase photo: ≤1.5 MB pre-compression, ~1200px longest edge, re-encoded;
  upload allowed only through the eligibility-checked backend;
- delete on ineligibility, admin removal, reset and account deletion.

Storage paths (Option A):

```text
profilePhotos/{uid}/avatar.webp                 (owner write)
showcasePhotos/{competitionId}/{uid}.webp       (backend write only)
```

Option B: use bounded Firestore data only if the compressed size is small and
the 1 GiB/egress quotas remain acceptable; otherwise choose an approved free media
store. Never rely on an unguessable URL as privacy.

---

## 8. Security rules (draft)

Files: `firestore.rules`, `storage.rules`, `firestore.indexes.json`.

They are **draft artifacts** for the trusted-backend architecture. Before any
real user data:

1. Run the Firebase Emulator Suite and write tests for every allow/deny branch.
2. Verify direct REST/SDK attempts cannot:
   - change `role`, `accountStatus`, `username`;
   - write submissions/showcases/audit/competitions;
   - read another user's reports or admin metadata;
   - upload a showcase image without backend approval;
   - exceed size/content-type limits.
3. Deploy with a dedicated project, App Check configured where supported, and
   billing/alerts if Option A.
4. Confirm that error messages and UI do not expose internal data.

Never deploy temporary open rules. Never add a “dev shortcut” that allows admin
writes from the browser.

---

## 9. Setup commands (once the architecture is chosen)

```bash
npm install -g firebase-tools
firebase login
firebase projects:list
# choose/create the project in the Firebase Console first:
#   - Authentication → Sign-in method → Email/Password: enable
#   - Firestore: create in production mode, choose a region
#   - App Check (recommended): register the web app
#   - Authorized domains: add <user>.github.io
```

Configure the web app values in `.env.local` (local) and GitHub repository
variables (deployment). Do **not** commit `.env.local`.

```bash
# after Option A is approved and functions exist:
firebase deploy --only firestore:rules,firestore:indexes
firebase deploy --only storage
firebase deploy --only functions

# emulator tests before touching production data:
firebase emulators:start --only auth,firestore,storage,functions
```

The CLI needs `firebase.json` (present) and, for functions, a `functions/`
package. `.firebaserc` is intentionally not committed; copy
`.firebaserc.example` and fill in the project ID locally.

---

## 10. Rollout sequence (Phase 2–4)

1. Choose Option A/B + username login approach; record the decision.
2. Create the Firebase project; enable Auth, Firestore (and Storage only if
   approved); configure authorized domains.
3. Implement auth service + username reservation + profile read/write; test in
   emulator and on the deployed Pages URL.
4. Seed the first competition window; implement read-only leaderboard queries
   with indexes.
5. Implement trusted confirmation and ranking; verify two browsers see one
   shared board and that direct writes are denied.
6. Implement profile-picture upload (Option A) or the approved free image path;
   test size limits and deletion.
7. Implement Top 10 showcase, locking, eligibility loss and cleanup; test the
   rank-10/rank-11 boundary and refresh bypass attempts.
8. Implement admin functions and audit; test unauthorized access.
9. Implement the reset routine and scheduler; run it twice, simulate a late run
   and a failed image delete.
10. Test at 360/390/768/1024/1440 px on real devices, test camera permissions on
    iOS/Android, then enable Pages deployment for production.
11. Monitor quotas; define alert thresholds and graceful quota messaging.

---

## 11. Open decisions checklist

- [ ] Option A (Blaze, free-quota discipline) or Option B (external free backend)?
- [ ] Username-only sign-in or email + password (public username)?
- [ ] Storage vs Firestore-embedded images (if Option B)?
- [ ] Reset scheduler: provider cron, GitHub Actions, or scheduled Function?
- [ ] Image re-analysis on the server available (required for genuine score
      verification)?
- [ ] Contact/ownership process for account deletion and moderation escalation?
- [ ] Retention period for audit records?
- [ ] Custom domain now or later?

Do not implement privileged features until these are answered. Phase 1 continues
to label everything correctly in the meantime.
