/**
 * useSettings — hook for loading and updating strategy/system settings.
 *
 * Provides:
 *   - `settings`       current SettingsResponse from the backend
 *   - `save(patch)`    validates locally, sends PUT, updates state
 *   - `reset()`        reload from backend discarding local changes
 *   - `isLoading`      initial fetch in progress
 *   - `isSaving`       PUT in progress
 *   - `error`          last error message
 *   - `successMessage` transient "saved" confirmation (clears after 3 s)
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { SettingsResponse, UpdateSettingsRequest } from '../types/api'
import { fetchSettings, updateSettings } from '../services/api'

export interface UseSettingsReturn {
  settings: SettingsResponse | null
  isLoading: boolean
  isSaving: boolean
  error: string | null
  successMessage: string | null
  save: (patch: UpdateSettingsRequest) => Promise<void>
  reset: () => Promise<void>
}

export function useSettings(): UseSettingsReturn {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const mountedRef = useRef(true)
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await fetchSettings()
      if (mountedRef.current) setSettings(data)
    } catch (err) {
      if (mountedRef.current)
        setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      if (mountedRef.current) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    load()
    return () => {
      mountedRef.current = false
      if (successTimerRef.current) clearTimeout(successTimerRef.current)
    }
  }, [load])

  // ── Local pre-validation ───────────────────────────────────────────────────
  const validate = (patch: UpdateSettingsRequest): string | null => {
    const current = settings

    const emaFast = patch.ema_fast ?? current?.ema_fast ?? 9
    const emaSlow = patch.ema_slow ?? current?.ema_slow ?? 21
    if (emaFast >= emaSlow) {
      return `EMA Fast (${emaFast}) must be less than EMA Slow (${emaSlow})`
    }

    const rsiOs = patch.rsi_oversold ?? current?.rsi_oversold ?? 30
    const rsiOb = patch.rsi_overbought ?? current?.rsi_overbought ?? 70
    if (rsiOs >= rsiOb) {
      return `RSI Oversold (${rsiOs}) must be less than RSI Overbought (${rsiOb})`
    }

    if (patch.ema_fast !== undefined && patch.ema_fast < 1) {
      return 'EMA Fast must be at least 1'
    }
    if (patch.ema_slow !== undefined && patch.ema_slow > 500) {
      return 'EMA Slow must be at most 500'
    }
    if (patch.rsi_length !== undefined && patch.rsi_length < 2) {
      return 'RSI Length must be at least 2'
    }
    if (patch.adx_min !== undefined && (patch.adx_min < 0 || patch.adx_min > 100)) {
      return 'Minimum ADX must be between 0 and 100'
    }
    if (
      patch.poll_interval_seconds !== undefined &&
      (patch.poll_interval_seconds < 10 || patch.poll_interval_seconds > 3600)
    ) {
      return 'Poll interval must be between 10 and 3600 seconds'
    }
    return null
  }

  // ── Save ──────────────────────────────────────────────────────────────────
  const save = useCallback(
    async (patch: UpdateSettingsRequest): Promise<void> => {
      setError(null)
      setSuccessMessage(null)

      // Client-side validation first
      const validationError = validate(patch)
      if (validationError) {
        setError(validationError)
        return
      }

      setIsSaving(true)
      try {
        const updated = await updateSettings(patch)
        if (!mountedRef.current) return
        setSettings(updated)
        setSuccessMessage('Settings saved successfully')
        if (successTimerRef.current) clearTimeout(successTimerRef.current)
        successTimerRef.current = setTimeout(() => {
          if (mountedRef.current) setSuccessMessage(null)
        }, 3000)
      } catch (err) {
        if (!mountedRef.current) return
        setError(err instanceof Error ? err.message : 'Failed to save settings')
      } finally {
        if (mountedRef.current) setIsSaving(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [settings]
  )

  // ── Reset (reload from server) ────────────────────────────────────────────
  const reset = useCallback(async (): Promise<void> => {
    setError(null)
    setSuccessMessage(null)
    await load()
  }, [load])

  return {
    settings,
    isLoading,
    isSaving,
    error,
    successMessage,
    save,
    reset,
  }
}
