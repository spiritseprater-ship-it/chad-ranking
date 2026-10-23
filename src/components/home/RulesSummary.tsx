import { Camera, ShieldCheck, Trophy } from 'lucide-react'
import { Link } from 'react-router-dom'
import { SectionHeading } from '@/components/ui/PageHeader'
import { ArrowRight } from 'lucide-react'

const ITEMS = [
  {
    icon: Camera,
    title: 'Photos are temporary',
    body: 'Only the three photos you capture for analysis are used. Raw scoring photos are not uploaded or archived; clearing browser memory cannot erase every possible device trace.',
  },
  {
    icon: Trophy,
    title: 'The Top 10 is exact',
    body: 'Eligibility is calculated from confirmed scores and the documented tie-breakers. If you fall below tenth, the showcase disappears and its stored image is scheduled for deletion.',
  },
  {
    icon: ShieldCheck,
    title: 'Humans moderate',
    body: 'Reports are private and reviewed by an administrator. An account is never banned automatically because a model — or a report — says so.',
  },
]

export function RulesSummary() {
  return (
    <section className="border-t border-line bg-canvas">
      <div className="container-page py-16 sm:py-20">
        <SectionHeading
          index="III."
          eyebrow="Fair play"
          title="Built for a small community, not a popularity contest."
          action={
            <Link
              to="/rules"
              className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-forest hover:underline underline-offset-4"
            >
              Read the rules
              <ArrowRight className="h-3 w-3" aria-hidden="true" />
            </Link>
          }
        />

        <div className="mt-10 grid gap-px overflow-hidden rounded-card border border-line bg-line md:grid-cols-3">
          {ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.title} className="bg-surface p-6 sm:p-7">
                <Icon className="h-4 w-4 text-forest" strokeWidth={1.5} aria-hidden="true" />
                <h3 className="mt-5 font-display text-base font-semibold text-ink">
                  {item.title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-muted">{item.body}</p>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
