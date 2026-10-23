import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { ProvisionalScore } from '@/types/domain'

/**
 * Holds ONLY the provisional score while the user reviews it.
 * Captured photos never enter this context and are revoked after analysis.
 */
export interface SubmissionDraft {
  provisional: ProvisionalScore
  competitionId: string
  photoCount: 3
}

interface DraftContextValue {
  draft: SubmissionDraft | null
  setDraft: (draft: SubmissionDraft) => void
  clearDraft: () => void
}

const DraftContext = createContext<DraftContextValue | null>(null)

export function SubmissionDraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraftState] = useState<SubmissionDraft | null>(null)
  const clearDraft = useCallback(() => setDraftState(null), [])
  const setDraft = useCallback((next: SubmissionDraft) => setDraftState(next), [])
  const value = useMemo(
    () => ({ draft, setDraft, clearDraft }),
    [draft, setDraft, clearDraft],
  )
  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>
}

export function useSubmissionDraft(): DraftContextValue {
  const context = useContext(DraftContext)
  if (!context) {
    throw new Error('useSubmissionDraft must be used inside <SubmissionDraftProvider>')
  }
  return context
}
