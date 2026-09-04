/**
 * useHealth — custom React hook that polls the backend health endpoint.
 *
 * Usage:
 *   const { data, status, error } = useHealth()
 */

import { useState, useEffect, useCallback } from 'react'
import { fetchHealth } from '../services/api'
import type { HealthResponse } from '../types/api'

type FetchStatus = 'idle' | 'loading' | 'success' | 'error'

interface UseHealthResult {
  data: HealthResponse | null
  status: FetchStatus
  error: string | null
  refetch: () => void
}

export function useHealth(pollIntervalMs = 10_000): UseHealthResult {
  const [data, setData] = useState<HealthResponse | null>(null)
  const [status, setStatus] = useState<FetchStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const check = useCallback(async () => {
    setStatus('loading')
    try {
      const result = await fetchHealth()
      setData(result)
      setStatus('success')
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    check()
    const interval = setInterval(check, pollIntervalMs)
    return () => clearInterval(interval)
  }, [check, pollIntervalMs])

  return { data, status, error, refetch: check }
}
