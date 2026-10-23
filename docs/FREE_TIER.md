# Free-tier notes — verified 23 October 2026

This document records the constraints that shaped Phase 1 and the Phase 2
options. Free tiers change; re-verify before implementation.

Primary sources:

- Firebase pricing: <https://firebase.google.com/pricing>
- Firebase pricing plans (Spark vs Blaze): <https://firebase.google.com/docs/projects/billing/firebase-pricing-plans>
- Cloud Storage requirement: Firebase documentation and pricing notes state that
  Cloud Storage for Firebase has required the Blaze plan since **3 February
  2026**. Do not assume the older “5 GB free on Spark” rule still applies.
- Cloud Functions deployment: requires Blaze. Blaze includes a monthly no-cost
  allowance (2M invocations, 400k GB-seconds, 200k CPU-seconds, 5 GB egress at
  the time of writing), but a billing account is required.
- GitHub Pages: static hosting, free for public repositories; no server-side
  code. GitHub Actions is free for public repositories; scheduled workflows can
  be delayed and may be disabled after prolonged repository inactivity.

## Current no-cost quotas (Spark, Firestore standard)

| Resource | No-cost allowance |
| --- | --- |
| Firestore stored data | 1 GiB |
| Firestore network egress | 10 GiB / month |
| Firestore document reads | 50,000 / day |
| Firestore document writes | 20,000 / day |
| Firestore document deletes | 20,000 / day |
| Email/Password Authentication | No-cost for a community of this size |
| Cloud Storage | **Not on Spark** — Blaze required |
| Cloud Functions | **Not on Spark** — Blaze required |
| Scheduled Functions | Blaze + Cloud Scheduler |
| GitHub Pages | Free for public repositories; static only |
| GitHub Actions | Free for public repositories; scheduling caveats |

Quotas are daily/monthly allowances, not lifetime promises.

## What this means for CHAD RANKING

1. **A ₹0 deployment cannot use Cloud Functions or Firebase Storage.**
   Authenticated confirmation, ranking, admin actions and cleanup need a trusted
   environment. The project must either approve Blaze (Option A, normally ₹0 in
   practice at this scale) or use a free external serverless backend (Option B).
2. **Images must be small.** A 1 GiB Firestore cap is shared with all documents.
   100 compressed avatars at 50 KB (~75 KB base64) is ~7.5 MB; a handful of
   weekly showcase images deleted on reset keeps usage small. Firestore egress
   (10 GiB/month) is the tighter constraint if every profile view downloads a
   200 KB image.
3. **Raw scoring photos are never stored.** They exist in browser memory and, in
   Phase 2, may be transferred transiently for server re-analysis. Never write
   them to Firestore or Storage.
4. **Reads dominate.** A leaderboard page should fetch:
   - the active competition pointer (1 read),
   - the Top 100 submissions (≤100 reads, ideally one query),
   - directory entries paginated (20–25 reads),
   - only the images needed for the visible Top 10.
   Avoid per-row profile document reads: denormalise the public username and
   avatar reference needed by the leaderboard into the returned view or a
   purpose-built read model, kept in sync by the backend.
5. **Weekly reset deletes, not archives.** This caps growth and matches privacy
   requirements, but deletion consumes the daily delete quota; keep batches
   small and idempotent.

## Estimated usage (100 participants)

| Operation | Approximate monthly usage |
| --- | --- |
| Confirmed entries | 100 / week = ~430 / month |
| Leaderboard reads | ~1,000 views × 100 docs = 100k reads (2 days of quota) |
| Profile reads | 1–2 per view |
| Showcase images | ≤10 active, deleted weekly; ~40 uploads + deletes/month |
| Storage (Option A) | ~10 MB avatars + transient showcase images |
| Auth | Tiny compared with the free MAU allowance |

A small community fits comfortably if reads are cached client-side briefly and
per-row reads are avoided. Instrument usage; do not guess.

## Graceful quota handling

Phase 2 requirements:

- Catch Firestore `resource-exhausted` / permission / unavailable codes and show a
  friendly, retryable message. Never show raw stack traces.
- Never silently drop a confirmed score: the confirmation call must return a
  definitive success/failure; retries are safe because the submission ID is
  deterministic.
- If a showcase image deletion fails, hide the content immediately, record a
  minimal operational cleanup status and retry; never expose the image.
- For quota or provider outages, display a banner explaining that the competition
  data is temporarily unavailable and that no score was changed.
- Do not auto-upgrade billing. Alert the owner.

## GitHub Pages specifics

- Static only: no secrets, no server routes, no scheduled jobs. The weekly reset
  cannot live here.
- Custom domain: add `public/CNAME` and set `VITE_BASE_PATH=/`.
- SPA refresh: `public/404.html` + `index.html` restore script. Project sites are
  detected by hostname; adjust for a user-site root.
- The deploy workflow uses official Pages actions and requires Pages to be set to
  “GitHub Actions” in repository settings.
- Deployment is not performed by Phase 1 changes.

## Cost-safety checklist for the owner

- [ ] Choose Option A or B before any backend work.
- [ ] If Blaze: set a low budget alert and a hard spending cap; monitor the first
      weeks; never leave an unbounded function.
- [ ] Keep images compressed and capped.
- [ ] Never store raw photos or previous leaderboards.
- [ ] Re-verify quotas before launch and after any provider change.
- [ ] Publish the entertainment disclaimer and moderation process.
