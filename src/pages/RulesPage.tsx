import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { FlaskConical, ShieldCheck } from 'lucide-react'
import { ENTERTAINMENT_DISCLAIMER, SCORING_CATEGORIES } from '@/config/constants'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { PageHeader } from '@/components/ui/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { Notice } from '@/components/ui/Notice'
import { BackendBanner } from '@/components/common/BackendBanner'

const SECTIONS = [
  { id: 'data-status', label: 'Data status' },
  { id: 'scoring', label: 'How scoring works' },
  { id: 'competition', label: 'Competition & ranking' },
  { id: 'showcase', label: 'Top 10 showcase' },
  { id: 'accounts', label: 'Accounts & usernames' },
  { id: 'privacy', label: 'Privacy' },
  { id: 'moderation', label: 'Moderation & reports' },
  { id: 'deletion', label: 'Account deletion' },
  { id: 'free-tier', label: 'Free-tier limits' },
]

function Section({
  id,
  index,
  title,
  children,
}: {
  id: string
  index: string
  title: string
  children: ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-24 border-b border-line py-8 first:pt-0 last:border-b-0">
      <div className="flex items-baseline gap-3">
        <span className="font-serif text-sm italic text-gold-deep">{index}</span>
        <h2 className="font-display text-xl font-semibold tracking-tight text-ink sm:text-2xl">
          {title}
        </h2>
      </div>
      <div className="mt-4 space-y-3 text-sm leading-relaxed text-muted">{children}</div>
    </section>
  )
}

export function RulesPage() {
  useDocumentTitle('Rules & privacy')

  return (
    <>
      <PageHeader
        eyebrow="The fine print, in plain language"
        title="Rules & privacy"
        description="How the competition works, what is public, what is temporary, and what this build does — and does not — do yet."
        actions={<Badge variant="outline">Phase 1 · frontend</Badge>}
      />

      <div className="container-page py-8 lg:py-10">
        <div className="grid gap-10 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <nav aria-label="On this page" className="hidden lg:block">
            <div className="sticky top-24">
              <p className="eyebrow">On this page</p>
              <ul className="mt-3 space-y-1.5">
                {SECTIONS.map((section) => (
                  <li key={section.id}>
                    <a
                      href={`#${section.id}`}
                      className="block rounded px-2 py-1.5 text-xs text-muted transition hover:bg-subtle hover:text-ink"
                    >
                      {section.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </nav>

          <div className="min-w-0 max-w-3xl">
            <Notice variant="info" title="This build is a frontend preview" className="mb-8">
              Authentication, cloud data, uploads, scoring confirmation, moderation and
              weekly resets are not connected to a backend yet. Items marked{' '}
              <span className="font-medium text-ink">Phase 2</span> describe the planned
              backend behaviour; they are not active today. Nothing here claims that
              security, scheduling or deletion has been tested against a live database.
            </Notice>

            <Section id="data-status" index="01" title="Data status">
              <BackendBanner />
              <ul className="list-disc space-y-1.5 pl-5">
                <li>
                  <span className="font-medium text-ink">Works in this build:</span> all
                  pages, responsive layouts, the three-photo browser workflow, local
                  image-quality analysis, demo-only in-memory accounts and actions.
                </li>
                <li>
                  <span className="font-medium text-ink">Not active:</span> Firebase
                  Authentication, Firestore leaderboard persistence, image uploads,
                  server-side confirmation, weekly reset scheduling and trusted admin
                  authorization.
                </li>
                <li>
                  Preview data is labelled “sample data” and resets when the browser tab
                  is reloaded. It is never presented as a real ranking.
                </li>
              </ul>
            </Section>

            <Section id="scoring" index="02" title="How scoring works">
              <p>
                CHAD SCORE is an entertainment score from 0 to 100. It is not a
                measurement of attractiveness, health, skin, hair, bone structure or
                personal worth, and it must never be treated as one.
              </p>
              <div className="overflow-hidden rounded-card border border-line bg-surface">
                <div className="grid grid-cols-[1fr_auto] border-b border-line px-4 py-2.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                  <span>Entertainment category</span>
                  <span>Weight</span>
                </div>
                {SCORING_CATEGORIES.map((category) => (
                  <div
                    key={category.category}
                    className="grid grid-cols-[1fr_auto] items-start gap-4 border-b border-line px-4 py-3 last:border-b-0"
                  >
                    <div>
                      <p className="text-xs font-medium text-ink">{category.label}</p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-muted">
                        {category.description}
                      </p>
                    </div>
                    <span className="text-xs font-semibold text-ink">
                      {Math.round(category.weight * 100)}%
                    </span>
                  </div>
                ))}
              </div>
              <p>
                The current preview uses a documented browser heuristic. It reads image
                properties — lighting, contrast, colour, detail and the visual variety
                between the three photos — and applies fixed weights. Two identical photo
                sets always produce the same score. It is not AI, it is not anthropometric
                analysis, and it uses no randomness.
              </p>
              <p>
                Very dark, blown-out, blurry or duplicate photos are rejected with a
                request to retake them instead of inventing a score. Phase 2 will
                re-validate the submitted score on the trusted backend; the browser
                cannot choose its own official score or rank.
              </p>
              <Notice variant="neutral">{ENTERTAINMENT_DISCLAIMER}</Notice>
              <p>
                Disputed results can be corrected only by an authorized administrator,
                with a recorded reason. The updated leaderboard is then recalculated from
                confirmed data.
              </p>
            </Section>

            <Section id="competition" index="03" title="Competition & ranking">
              <p>
                The competition runs from Monday 00:00 to the following Monday 00:00 in
                Asia/Kolkata (IST). Weeks are derived from a trusted server timestamp and
                a server-controlled competition identifier, never from a label typed into
                the browser.
              </p>
              <ul className="list-disc space-y-1.5 pl-5">
                <li>Exactly three photos make a complete attempt. Retakes are allowed before confirmation.</li>
                <li>Only one confirmed score per account is counted each week. Confirmed scores lock until reset.</li>
                <li>
                  Ranking order: confirmed score descending → earlier confirmation time
                  ascending → stable account identifier ascending.
                </li>
                <li>Ranks 1–100 form the official leaderboard. Ranks below 100 appear in a separate directory by username only.</li>
                <li>Ties are not shared; the order above is deterministic.</li>
              </ul>
              <p>
                Countdowns use the active competition’s end timestamp returned by the
                backend. If a scheduled reset runs late, the previous competition is still
                treated as expired and cannot accept new confirmations.
              </p>
            </Section>

            <Section id="showcase" index="04" title="Top 10 showcase">
              <p>
                Ranks 1–10 unlock the exclusive showcase. Rank 1 is titled TRUE ADAM, ranks
                2–3 ELITE CHAD, and ranks 4–10 TOP 10. These are fictional competition
                labels.
              </p>
              <ul className="list-disc space-y-1.5 pl-5">
                <li>Eligible participants may add one optional slogan (up to 120 characters) and one optional showcase photograph.</li>
                <li>Once submitted, the showcase is locked for the week. It cannot be edited or replaced from the browser.</li>
                <li>If the participant leaves the Top 10, the showcase is hidden immediately and its stored image is scheduled for real deletion — not just hidden in the interface.</li>
                <li>The weekly reset deletes previous-week slogans and images. No showcase archive is kept.</li>
                <li>Administrators may remove inappropriate showcase content at any time.</li>
              </ul>
              <p>
                The normal profile picture is separate from the showcase photo and persists
                across resets. Showcase content is public only while eligibility is
                confirmed by the backend.
              </p>
            </Section>

            <Section id="accounts" index="05" title="Accounts & usernames">
              <p>
                Registration requires a unique username, a password and an email address
                used privately by Firebase Authentication. Usernames are compared
                case-insensitively, limited to letters, numbers and underscores, and
                checked against reserved and impersonation-sensitive names.
              </p>
              <p>
                Choose a username close to the name your friends recognise you by. Do not
                impersonate another person or public figure. Your legal name is not
                required, and a username is not verified against any legal identity.
              </p>
              <p>
                Passwords are handled by Firebase Authentication once connected; this
                project never stores plaintext passwords and never puts service-account
                credentials in the frontend. Client-side role flags, scores and ranks are
                never trusted — every protected action is re-checked by the backend.
              </p>
              <p>
                <span className="font-medium text-ink">Phase 2 note:</span> Firebase
                username-only sign-in needs a private username-to-account resolution step.
                The supported pattern and its free-tier trade-offs are documented in the
                repository README; the login form currently accepts a username or email so
                the interface stays stable either way.
              </p>
            </Section>

            <Section id="privacy" index="06" title="Privacy">
              <p>
                <span className="font-medium text-ink">Public:</span> username, chosen
                profile picture, current confirmed score, current rank, rank title, and —
                only while eligible — the submitted slogan and showcase photograph.
              </p>
              <p>
                <span className="font-medium text-ink">Private:</span> email address,
                authentication credentials and tokens, moderation notes, internal audit
                records, account status details, and raw scoring photos. None of these are
                rendered on public pages.
              </p>
              <ul className="list-disc space-y-1.5 pl-5">
                <li>Scoring photos are held in browser memory, analysed locally, and released on analysis, retake or leaving the page. They are not uploaded or written to the database.</li>
                <li>No raw-photo history or hidden archive is kept. Clearing memory is not equivalent to securely erasing every possible browser, operating-system or network trace.</li>
                <li>Only a confirmed score and minimal submission metadata are stored. Moderation reports store a category, reporter, reported account, status and time — no screenshots.</li>
                <li>Profile pictures are persistent until replaced or deleted; weekly resets do not remove them.</li>
                <li>Showcase slogans and photos are deleted when eligibility ends and are not carried into the next week.</li>
                <li>Participant photographs are never used for unrelated purposes, advertising, or model training by this project.</li>
              </ul>
              <p>
                <span className="font-medium text-ink">Phase 2 note:</span> Firebase
                Security Rules and Storage Rules will restrict reads and writes per
                feature before real user data is enabled. Web configuration values are
                public; they are not a security boundary.
              </p>
            </Section>

            <Section id="moderation" index="07" title="Moderation & reports">
              <p>
                Signed-in participants can report impersonation, fake profiles,
                inappropriate images, offensive content or spam from a public profile. To
                protect privacy, pending reports are visible only to administrators, and
                a report alone never bans an account.
              </p>
              <p>
                Administrators review reports by hand. Suspension, content removal,
                disqualification or dismissal is always a human decision. No automated
                system declares a profile fake, and no AI model is used to judge identity.
                Duplicate reports and basic rate limits are enforced in the backend.
              </p>
            </Section>

            <Section id="deletion" index="08" title="Account deletion">
              <p>
                Account deletion is currently owner-assisted. Open a deletion request in
                the project repository and include your username; never post your password
                or email publicly. The owner verifies the request through the repository
                account used for the competition community.
              </p>
              <p>
                <span className="font-medium text-ink">Phase 2:</span> deletion will remove
                the account record, username reservation, profile picture and any active
                showcase image. Minimal audit records may be retained for a short,
                documented period to maintain moderation accountability. No self-service
                deletion button is claimed until it is actually implemented.
              </p>
            </Section>

            <Section id="free-tier" index="09" title="Free-tier limits">
              <p>
                Firebase quotas verified in October 2026 for the free Spark plan:
                Firestore includes 1 GiB stored, 50,000 document reads per day, 20,000
                writes per day and 20,000 deletes per day. Email/password authentication is
                available without cost for small communities. These limits can change and
                are not lifetime promises.
              </p>
              <ul className="list-disc space-y-1.5 pl-5">
                <li>
                  <span className="font-medium text-ink">Cloud Functions is not available on Spark.</span>{' '}
                  It requires the Blaze plan with billing enabled. This project does not
                  enable billing silently.
                </li>
                <li>
                  <span className="font-medium text-ink">Cloud Storage requires Blaze since 3 February 2026.</span>{' '}
                  The ₹0 plan therefore avoids Firebase Storage; compressed images will use
                  a free-compatible path documented in the repository, or remain disabled
                  until the owner explicitly enables billing.
                </li>
                <li>
                  Scheduled resets must not depend on a browser. Phase 2 uses a trusted
                  scheduler outside the visitor’s browser (for example a free GitHub Actions
                  scheduled workflow) calling an idempotent, authorized reset routine. GitHub
                  schedules can be delayed and are disabled after prolonged repository
                  inactivity, so the application also derives expiry from timestamps.
                </li>
                <li>
                  If quotas are reached, the interface shows an explanation rather than
                  silently discarding a confirmed score.
                </li>
              </ul>
              <div className="flex items-start gap-2.5 rounded-lg border border-gold/25 bg-gold-tint/40 px-4 py-3">
                <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gold-deep" aria-hidden="true" />
                <p className="text-[11px] leading-relaxed text-muted">
                  The exact setup and remaining configuration steps live in the repository
                  README and docs. Nothing on this page should be read as a claim that a
                  live deployment, scheduler or security-rules test has already passed.
                </p>
              </div>
            </Section>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to="/leaderboard"
                className="inline-flex h-10 items-center rounded-field bg-forest px-4 text-[11px] font-semibold uppercase tracking-[0.08em] text-white hover:bg-forest-700"
              >
                View the leaderboard
              </Link>
              <Link
                to="/"
                className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted hover:text-ink"
              >
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                Back to home
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
