import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'

export interface AsyncState<T> {
  data: T | undefined
  error: ApiError | null
  loading: boolean
  reload: () => void
  setData: (value: T | ((current: T | undefined) => T | undefined)) => void
}

/**
 * Load data whenever `deps` change. Stale responses are dropped, and the last good data
 * stays on screen while a reload is in flight.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[], enabled = true): AsyncState<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [version, setVersion] = useState(0)
  const loader = useRef(load)
  loader.current = load

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    loader.current(controller.signal).then(
      (value) => {
        if (controller.signal.aborted) return
        setData(value)
        setError(null)
        setLoading(false)
      },
      (reason) => {
        if (controller.signal.aborted) return
        setError(reason instanceof ApiError ? reason : new ApiError(0, 'Something went wrong. Please try again.'))
        setLoading(false)
      },
    )
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, version])

  const reload = useCallback(() => setVersion((value) => value + 1), [])
  return { data, error, loading, reload, setData }
}
