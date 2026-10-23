import { Camera, Crown, ListOrdered, ScanFace, UserPlus } from 'lucide-react'
import { SectionHeading } from '@/components/ui/PageHeader'

const STEPS = [
  {
    index: '01',
    title: 'Create your account',
    body: 'Choose a username your friends recognise. No legal name is required, and your email is never shown publicly.',
    icon: UserPlus,
  },
  {
    index: '02',
    title: 'Capture three photos',
    body: 'Use the live camera or upload. Photos are analysed in your browser and are not added to a permanent archive.',
    icon: Camera,
  },
  {
    index: '03',
    title: 'Review and confirm',
    body: 'You receive a provisional entertainment score. Retry as often as you like, then post one confirmed result.',
    icon: ScanFace,
  },
  {
    index: '04',
    title: 'Compete on the board',
    body: 'Every confirmed score is ranked against the community. Ties break by earlier submission, then a stable account ID.',
    icon: ListOrdered,
  },
  {
    index: '05',
    title: 'Unlock the Top 10',
    body: 'The top ten unlock the exclusive showcase. Rank first and the week belongs to you as TRUE ADAM.',
    icon: Crown,
    accent: true,
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-24 border-t border-line bg-surface">
      <div className="container-page py-16 sm:py-20">
        <SectionHeading
          index="I."
          eyebrow="How it works"
          title="Five steps. One week. One rank."
          description="A simple weekly loop designed for a small community — not an endless feed."
        />

        <ol className="mt-10 grid gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((step) => {
            const Icon = step.icon
            return (
              <li
                key={step.index}
                className="relative flex flex-col bg-canvas p-5 sm:p-6"
              >
                <div className="flex items-center justify-between">
                  <span className="font-serif text-lg italic text-gold-deep">
                    {step.index}
                  </span>
                  <Icon
                    className="h-4 w-4 text-muted"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                </div>
                <h3 className="mt-7 font-display text-[0.9375rem] font-semibold leading-snug text-ink">
                  {step.title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-muted">{step.body}</p>
                {step.accent ? (
                  <span className="mt-4 inline-flex w-fit rounded-full border border-gold/30 bg-gold-tint px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-gold-deep">
                    Top 10 exclusive
                  </span>
                ) : null}
              </li>
            )
          })}
        </ol>

        <p className="mt-5 max-w-3xl text-[11px] leading-relaxed text-muted">
          Scores are fictional competition categories — pose & presentation,
          expression & confidence, creativity, and styling. They are entertainment,
          not an assessment of appearance, health, or personal worth.
        </p>
      </div>
    </section>
  )
}
