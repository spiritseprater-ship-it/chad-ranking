import { Check } from 'lucide-react'
import { cn } from '@/utils/cn'

const STEPS = [
  { id: 1, label: 'Capture three photos' },
  { id: 2, label: 'Review provisional score' },
  { id: 3, label: 'Confirm & post' },
]

export function SubmissionSteps({ current }: { current: 1 | 2 | 3 }) {
  return (
    <ol className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6" aria-label="Submission steps">
      {STEPS.map((step, index) => {
        const complete = step.id < current
        const active = step.id === current
        return (
          <li key={step.id} className="flex flex-1 items-center gap-3">
            <span
              className={cn(
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold tabular-nums',
                complete && 'border-forest bg-forest text-white',
                active && 'border-forest text-forest',
                !complete && !active && 'border-line text-muted',
              )}
              aria-current={active ? 'step' : undefined}
            >
              {complete ? <Check className="h-3 w-3" aria-hidden="true" /> : step.id}
            </span>
            <span
              className={cn(
                'text-[10px] font-semibold uppercase tracking-[0.1em]',
                active ? 'text-ink' : 'text-muted',
              )}
            >
              {step.label}
            </span>
            {index < STEPS.length - 1 ? (
              <span className="ml-auto hidden h-px flex-1 bg-line sm:block" aria-hidden="true" />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
