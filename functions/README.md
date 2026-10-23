# Cloud Functions (Phase 2 — not implemented)

This folder is reserved for trusted Firebase Cloud Functions if the project
chooses the Blaze plan in Phase 2.

## Important limitation

As verified in October 2026, **Cloud Functions cannot be deployed on the Spark
(free) plan**; deployment requires the Blaze pay-as-you-go plan with a billing
account. The Spark plan still includes no-cost quotas for Firestore and
Authentication, but a card must be on file for Functions.

Do not enable billing without the repository owner's explicit approval. See
[`docs/FIREBASE_PLAN.md`](../docs/FIREBASE_PLAN.md) for the two viable Phase 2
architectures, including a strictly ₹0 option that uses an external free
serverless backend instead of Functions.

## Planned callable functions

| Function                 | Purpose                                                         |
| ------------------------ | --------------------------------------------------------------- |
| `confirmSubmission`      | Validate active competition, eligibility, lock and score; write the confirmed submission; derive the rank from authoritative data. |
| `submitShowcase`         | Re-check Top 10 eligibility; validate slogan/photo; lock the showcase. |
| `adminAction`            | Re-check the admin role; apply suspension, corrections, removals; append the audit record. |
| `resolveReport`          | Admin-only moderation decision.                                  |
| `resetCompetition`       | Idempotent weekly reset, also callable by the scheduler.         |
| `cleanupShowcase`        | Delete showcase records and stored images when eligibility ends. |

No service-account credentials may ever be placed in this repository or in the
frontend bundle. Functions use the runtime service account automatically.
