import { ChevronLeft, ChevronRight } from 'lucide-react'

export function Pagination({
  page,
  pageCount,
  onPageChange,
  label = 'Pagination',
}: {
  page: number
  pageCount: number
  onPageChange: (page: number) => void
  label?: string
}) {
  if (pageCount <= 1) return null
  return (
    <nav
      aria-label={label}
      className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5"
    >
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:border-forest/25 hover:text-ink disabled:pointer-events-none disabled:opacity-40"
      >
        <ChevronLeft className="h-3 w-3" aria-hidden="true" />
        Previous
      </button>
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted" aria-live="polite">
        Page {page} of {pageCount}
      </p>
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= pageCount}
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted transition hover:border-forest/25 hover:text-ink disabled:pointer-events-none disabled:opacity-40"
      >
        Next
        <ChevronRight className="h-3 w-3" aria-hidden="true" />
      </button>
    </nav>
  )
}
