# Verification status

Honest record of what was exercised in Phase 1 and what still needs a human.
Last verified: 23 October 2026.

## Automated checks

```bash
npm run build   # strict TypeScript project build + Vite production build
npm run smoke   # service-layer and server-render checks
npm run ci      # both
```

`npm run smoke` boots Vite in middleware mode, loads the real modules through
`ssrLoadModule`, and asserts:

**Ranking**

- exactly 100 ranked positions;
- scores are non-increasing;
- rank titles match `1 / 2–3 / 4–10 / 11–100`;
- suspended and unconfirmed entries are excluded;
- equal scores break by earlier `submittedAt`, then by UID;
- unranked participants receive “NOT YET RANKED”.

**Accounts**

- username availability is case-insensitive;
- reserved names are rejected;
- sign-in works by username and by email;
- suspended accounts cannot sign in.

**Submissions**

- a new week allows exactly one submission;
- `confirmSubmission` rejects a second attempt with `already-confirmed`;
- the weekly status reports rank, score and title after confirmation.

**Showcase**

- only the Top 10 are eligible;
- the first submission locks the showcase;
- a second submission fails with `showcase-locked`;
- leaving the Top 10 hides the showcase.

**Administration**

- non-admins receive `forbidden` for every admin operation;
- corrections write an audit record;
- report decisions write an audit record;
- reasons shorter than three characters are rejected;
- destructive actions require explicit confirmation in the UI.

**Rendering**

- all thirteen routes server-render without throwing, including `/admin`
  (access-denied path), `/profile/:username` and the 404 route.

**Not covered by this harness**

- real browser layout, hover/focus rendering, camera permissions, native file
  pickers, object-URL cleanup in a live tab;
- Firebase behaviour (nothing is configured);
- accessibility tooling and real screen readers;
- visual regression at each breakpoint.

## Manual verification still required

| Check | Status | Notes |
| --- | --- | --- |
| Desktop layout (1440 px) | ⚠️ Not run | No browser binary available in the build environment |
| Laptop (1024 px) | ⚠️ Not run | |
| Tablet (768 px) | ⚠️ Not run | |
| Mobile (390 px) | ⚠️ Not run | |
| Small mobile (360 px) | ⚠️ Not run | |
| Keyboard-only navigation | ⚠️ Not run | Focus styles are implemented; needs a pass |
| Reduced motion | ⚠️ Not run | `prefers-reduced-motion` disables animations |
| Camera on iOS Safari / Android Chrome | ⚠️ Not run | Requires HTTPS and a real device |
| Screen reader announcement of the countdown | ⚠️ Not run | Countdown updates should be non-live by default |
| Colour contrast | ✅ Audited | Token-level checks against WCAG AA; muted/gold/warning were darkened |
| Deep-link refresh on GitHub Pages | ⚠️ Not run | Requires an actual Pages deployment |
| Production `base` path correctness | ⚠️ Not run | Requires a real repository name on Actions |

Responsive behaviour was implemented with mobile-first breakpoints and reviewed
in code, but **it has not been visually verified**. A human should inspect the
preview at the breakpoints above, and a real device test is required before
accepting camera capture as working.

## How to test locally with sample data

```bash
printf 'VITE_ENABLE_DEMO_PREVIEW=true\n' > .env.local
npm run dev
```

Then walk these paths:

1. `/` — hero, weekly panel, Top 10 preview, rules summary.
2. `/signup` — validation, live username check, reserved-name rejection.
3. `/login` as `Challenger` → `/dashboard` → `/submit`.
4. Capture or upload three photos → review provisional score → confirm.
5. Confirm again in a second tab: must show “already confirmed”, never a second
   entry.
6. `/leaderboard` — Top 10 cards, official Top 100 pagination, tie-breaks.
7. `/participants` — search, pagination, suspended accounts absent.
8. `/profile/Challenger` — provisional state, no showcase.
9. `/login` as `Zaid` → `/showcase` — locked card, not editable.
10. `/login` as `Aarav_Admin` → `/admin` — stats, corrections, moderation,
    audit. Every destructive action must ask for confirmation.
11. `/rules` — all anchors resolve; privacy and free-tier statements.
12. `/does-not-exist` — 404 with routes back into the app.
13. Reload on every page: no blank screen, no lost session in the same tab.

Try 360 px width with browser zoom at 100 %: no horizontal scrolling except
tables explicitly designed to scroll inside a labelled region.

## What “ready for Phase 2” means

- Build and smoke checks pass.
- A human has approved the layout at all five widths.
- Firebase project, Auth, Firestore and (if approved) Storage exist.
- Security rules have passed emulator tests.
- Trusted confirmation and reset are implemented and tested twice, including a
  late run.
- Quotas and graceful failure paths are observed in a staging project.
