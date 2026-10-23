import { useEffect, useRef, useState } from 'react'
import type { AppError } from '@/services/errors'
import { toAppError } from '@/services/errors'

export interface AsyncResult<T> {
  data: T | null
  error: AppError | null
  loading: boolean
  reload: () => void
}

/**
 * Small data-loading helper with request de-duplication. Callers pass explicit
 * dependency values; the latest task closure is always used.
 */
export function useAsync<T>(task: () => Promise<T>, deps: unknown[]): AsyncResult<T> {
  const taskRef = useRef(task)
  taskRef.current = task

  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<AppError | null>(null)
  const [loading, setLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    Promise.resolve()
      .then(() => taskRef.current())
      .then((result) => {
        if (!active) return
        setData(result)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (!active) return
        setError(toAppError(cause))
        setLoading(false)
      })

    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey, ...deps])

  return {
    data,
    error,
    loading,
    reload: () => setReloadKey((key) => key + 1),
  }
}
