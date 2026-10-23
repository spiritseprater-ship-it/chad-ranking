# Phase 2 — Firestore schema, trust boundaries and rules

Status: **rules, schema, indexes and emulator tests implemented and run in CI.**
The Cloudflare Worker that performs privileged writes is **not implemented yet**;
nothing below claims the app is live.

Approved decisions (October 2026): Spark plan only, email + password auth with a
public username, official scores recomputed by a Cloudflare Worker, compressed
images stored in Firestore, optional email verification, App Check in monitoring
mode, 90-day audit / 30-day report retention.

---

## 1. Trust boundary

```
Browser (React SPA)
  ├─ Firebase Auth SDK ............ identities and ID tokens
  ├─ Firestore SDK (reads) ........ public leaderboard/profile data
  └─ small, self-owned writes ..... profile, username, avatar, reports
        │
        │  rules deny everything privileged
        ▼
Cloudflare Worker (trusted, holds a Firestore-scoped service account)
  └─ Admin SDK writes ............. submissions, showcases, images,
                                    competitions, audit, rate limits
```

The repository contains **no** service-account key. The Worker secret is stored
in Cloudflare, never here, never in the bundle.

Consequences enforced by `firestore.rules`:

- A browser cannot write a score, rank, showcase, competition, audit entry or
  rate-limit counter.
- A browser cannot change its own `role` or `accountStatus`.
- A browser cannot read another user's reports, the audit trail or rate limits.
- Every collection not explicitly listed is denied by the catch-all rule.

---

## 2. Collections

All timestamps are Firestore `Timestamp`s. Field names are exactly as enforced by
the rules and asserted in `tests/rules/firestore.rules.test.mjs`.

### `users/{uid}` — public profile

| Field | Type | Notes |
|---|---|---|
| `uid` | string | must equal the document ID and `request.auth.uid` |
| `username` | string | `^[A-Za-z0-9_]{3,20}$`, reserved names blocked |
| `usernameLowercase` | string | must equal `username.lower()` |
| `profileImagePath` | string \| null | pointer only, e.g. `profileImages/{uid}` |
| `createdAt` | timestamp | must equal `request.time` on create |
| `role` | `'member' \| 'admin'` | **immutable from the client** |
| `accountStatus` | `'active' \| 'suspended'` | **immutable from the client** |

- Read: public. Create: owner only, `role` forced to `member`.
- Update: owner may change **only** `profileImagePath`.
- Delete: denied (account deletion runs through the Worker).
- Email addresses live in Firebase Authentication, never in this document.

### `usernames/{usernameLowercase}` — uniqueness reservation

| Field | Type | Notes |
|---|---|---|
| `uid` | string | must equal `request.auth.uid` |
| `usernameLowercase` | string | must equal the document ID |
| `createdAt` | timestamp | server timestamp |

- Document ID is the lowercased username, so Firestore enforces case-insensitive
  uniqueness atomically.
- Created in the same transaction as `users/{uid}` and `profileImages` pointer.
- Update/delete: denied.

### `profileImages/{uid}` — compressed avatar

| Field | Type | Limit |
|---|---|---|
| `uid` | string | equals document ID |
| `mime` | string | `image/webp`, `image/jpeg` or `image/png` |
| `data` | string (base64) | ≤ 65,536 characters |
| `bytes` | number | 1 – 49,152 |
| `width`, `height` | number | 64 – 1,024 px |
| `updatedAt` | timestamp | server timestamp |

- Read: public. Write: owner, active account, **one update per hour**
  (`request.time > updatedAt + 1h`).
- Storage is Blaze-only, so images are bounded Firestore documents. SVG is
  rejected; the client re-encodes through a canvas, which also strips EXIF.

### `competitions/{competitionId}` — week window

```text
competitionId: "w2026-10-19"   (Monday 00:00 IST → next Monday 00:00 IST)
startsAt, endsAt: Timestamp
status: 'active' | 'closed'
timezone: 'Asia/Kolkata'
```

- Read: public. Write: **Worker only**.
- The ID is derivable from the clock, so a client cannot invent or extend a week.

### `submissions/{competitionId}_{uid}` — official entry

| Field | Type | Notes |
|---|---|---|
| `uid` | string | owner |
| `competitionId` | string | `wYYYY-MM-DD` |
| `confirmedScore` | number | integer 0–100, recomputed by the Worker |
| `breakdown` | map | pose / expression / creativity / styling |
| `submittedAt` | timestamp | Worker clock |
| `scoringVersion` | string | e.g. `local-heuristic-v1` |
| `evidenceHash` | string | SHA-256 of the submitted pixel buffers |
| `moderationStatus` | string | `clear` \| `under_review` \| `disqualified` |
| `disqualificationReason` | string \| null | set only by the Worker |

- Read: public. Write: **denied** for every client.
- One document per user per week, enforced by the deterministic ID plus a
  create-if-absent precondition in the Worker.

### `showcases/{competitionId}_{uid}` — Top 10 showcase

```text
uid, competitionId, slogan, imageId, status: 'locked' | 'removed',
rank (1–10 at submission time), submittedAt
```

- Read: only while `status == 'locked'`.
- Write: **denied** for every client. Removed or expired showcases disappear from
  reads immediately, even before the cleanup job deletes them.

### `showcaseImages/{competitionId}_{uid}` — compressed showcase photo

```text
uid, competitionId, mime, data (base64), bytes, width, height
```

- Read: only when the linked `showcases/{sameId}` exists and is `locked`.
- Write: **denied** (Worker only, after an eligibility check).

### `reports/{reporterUid}_{reportedUid}` — private moderation queue

```text
reporterUid, reportedUid, category, status: 'pending' | 'actioned' | 'dismissed',
createdAt
```

- Create: a signed-in active member may file **one** report per target; the
  document ID must equal `reporterUid + '_' + reportedUid`, which makes duplicates
  impossible and blocks forged IDs. Self-reports are rejected.
- Categories are a closed list: `impersonation`, `fake-profile`,
  `inappropriate-image`, `offensive-content`, `spam`. No free text, so private
  information cannot be parked in the database.
- Read/update: **admin only**; only `status` may change.
- Delete: denied (30-day retention handled by the Worker).

### `adminAudit/{eventId}` — trusted trail

```text
actionType, actorUid, targetUid, reason, createdAt
```

- Read: admin only. Write: **denied** (Worker only). 90-day retention.

### `rateLimits/{uid}` — Worker counters

- Read/write: **denied for everybody**, including admins. Only the Worker's
  service account touches this collection.

---

## 3. Composite indexes

`firestore.indexes.json` declares exactly the queries Phase 2 needs:

| Collection | Fields | Used by |
|---|---|---|
| `submissions` | `competitionId` ↑, `moderationStatus` ↑, `confirmedScore` ↓, `submittedAt` ↑, `uid` ↑ | Top 100 and rank derivation |
| `showcases` | `competitionId` ↑, `status` ↑, `rank` ↑ | Top 10 showcase read |
| `reports` | `status` ↑, `createdAt` ↓ | moderation queue |

Tie-breaking is always `confirmedScore` desc → `submittedAt` asc → `uid` asc, so
the index order matches `compareSubmissions()` in `src/utils/ranking.ts`.

Do not add indexes speculatively. Firestore reports the exact missing index when a
query first runs, and the deploy is part of Phase 2 setup.

---

## 4. Rules invariants covered by tests

`tests/rules/firestore.rules.test.mjs` runs against the emulator with a `demo-*`
project ID (no credentials, no billing) and asserts, among others:

- anonymous and cross-account writes are denied;
- `role`/`accountStatus` cannot be self-assigned or changed;
- usernames are validated, reservation is owner-only and immutable;
- avatar size, MIME type, dimensions and the one-hour cooldown are enforced;
- every client write to submissions, showcases, showcase images, competitions,
  audit and rate limits is denied;
- a removed showcase and its image become unreadable immediately;
- reports are one-per-pair, self-reports are denied, members cannot read the
  queue, suspended admins lose access, admins may only change `status`;
- unknown collections fall through to deny.

Run locally (requires Java for the Firestore emulator):

```bash
npm run test:rules
npm run emulators      # start only the emulator, e.g. for manual probing
```

CI runs the same suite on every pull request
(`.github/workflows/ci.yml` → `firestore-rules`).

---

## 5. What is deliberately not stored

- Email addresses (Authentication only).
- Raw scoring photos, thumbnails or analysis metrics.
- Previous weeks' leaderboards or winner archives.
- Free-text moderation notes or accusations.
- Passwords, tokens or service-account credentials.
- Full-resolution showcase images (compressed WebP only).

---

## 6. Still to build (Phase 2, steps 2+)

1. Worker: ID-token verification, Firestore REST writes, score recomputation.
2. Auth wiring: sign-up transaction, username reservation, password reset.
3. Avatar upload through the browser encoder.
4. Leaderboard/showcase reads against the real schema.
5. Admin operations, audit writes, cleanup and retention jobs.
6. App Check in monitoring mode.

Until those exist, the app continues to run its labelled demo layer and must not
be described as connected.

### Known limitation (approved, must be documented in the UI)

The Worker recomputes the score from three 96×96 pixel buffers sent by the
browser. It guarantees that **the client does not choose the number**, but it
cannot prove the photos were captured live by a camera. Displayed copy must say
so; reports, the public Top 10 showcase and admin disqualification are the
human checks.
