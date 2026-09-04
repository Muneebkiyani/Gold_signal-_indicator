import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  IndicatorsResponse,
  MarketResponse,
  SignalCurrentResponse,
  SignalRecord,
  StatusResponse,
  StreamMessage,
} from '../types/api'
import {
  fetchCurrentSignal,
  fetchIndicators,
  fetchMarket,
  fetchSignals,
  fetchStatus,
} from '../services/api'

export type StreamConnectionStatus = 'LIVE' | 'RECONNECTING' | 'OFFLINE'

export function useTradingData(pollIntervalMs = 12000) {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [market, setMarket] = useState<MarketResponse | null>(null)
  const [indicators, setIndicators] = useState<IndicatorsResponse | null>(null)
  const [currentSignal, setCurrentSignal] = useState<SignalCurrentResponse | null>(null)
  const [signalsHistory, setSignalsHistory] = useState<SignalRecord[]>([])
  const [totalSignals, setTotalSignals] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(10)

  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [streamStatus, setStreamStatus] = useState<StreamConnectionStatus>('RECONNECTING')

  const mountedRef = useRef(true)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Baseline REST Data Fetcher ──────────────────────────────────────────────
  const loadRestData = useCallback(
    async (showLoadingSpinner = false) => {
      if (showLoadingSpinner) {
        setIsRefreshing(true)
      }

      try {
        const [
          statusRes,
          marketRes,
          indicatorsRes,
          signalRes,
          historyRes,
        ] = await Promise.all([
          fetchStatus().catch(() => null),
          fetchMarket().catch(() => null),
          fetchIndicators().catch(() => null),
          fetchCurrentSignal().catch(() => null),
          fetchSignals(pageSize, page * pageSize).catch(() => ({
            items: [],
            total: 0,
            limit: pageSize,
            offset: page * pageSize,
          })),
        ])

        if (!mountedRef.current) return

        if (statusRes) {
          setStatus(statusRes)
          setError(null)
        } else {
          setStreamStatus('OFFLINE')
          setError('Backend service unreachable')
        }

        if (marketRes) setMarket(marketRes)
        if (indicatorsRes) setIndicators(indicatorsRes)
        if (signalRes) setCurrentSignal(signalRes)
        if (historyRes) {
          setSignalsHistory(historyRes.items)
          setTotalSignals(historyRes.total)
        }

        setLastUpdated(new Date())
      } catch (err) {
        if (!mountedRef.current) return
        setError(err instanceof Error ? err.message : 'Failed to fetch trading data')
        setStreamStatus('OFFLINE')
      } finally {
        if (mountedRef.current) {
          setIsLoading(false)
          setIsRefreshing(false)
        }
      }
    },
    [page, pageSize]
  )

  // ── Server-Sent Events (SSE) Stream ─────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true

    const connectSSE = () => {
      if (!mountedRef.current) return

      const rawApi = import.meta.env.VITE_API_URL?.trim()
      const normalizedApi = rawApi
        ? (rawApi.startsWith('http') ? rawApi : `https://${rawApi}`).replace(/\/+$/, '')
        : ''
      const streamUrl = normalizedApi ? `${normalizedApi}/api/stream` : '/api/stream'

      const es = new EventSource(streamUrl)
      eventSourceRef.current = es

      es.onopen = () => {
        if (!mountedRef.current) return
        setStreamStatus('LIVE')
        setError(null)
      }

      es.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const data: StreamMessage = JSON.parse(event.data)
          const payload = data.payload

          if (payload.market) {
            setMarket(payload.market)
          }
          if (payload.indicators) {
            setIndicators(payload.indicators)
          }
          if (payload.current_signal) {
            setCurrentSignal(payload.current_signal)
          }
          if (payload.status) {
            setStatus(payload.status)
          }
          if (payload.new_signals && payload.new_signals.length > 0) {
            // Instantly prepend newly occurred signals to table
            setSignalsHistory((prev) => {
              const existingIds = new Set(prev.map((s) => s.id ?? s.candle_time))
              const toAdd = payload.new_signals!.filter(
                (s) => !existingIds.has(s.id ?? s.candle_time)
              )
              return [...toAdd, ...prev].slice(0, pageSize)
            })
            setTotalSignals((prev) => prev + payload.new_signals!.length)
          }

          setStreamStatus('LIVE')
          setLastUpdated(new Date())
          setIsLoading(false)
        } catch {
          // Non-JSON or keep-alive ping
        }
      }

      es.onerror = () => {
        if (!mountedRef.current) return
        setStreamStatus('RECONNECTING')
        es.close()
        eventSourceRef.current = null

        // Attempt reconnection after 3 seconds
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = setTimeout(() => {
          connectSSE()
        }, 3000)
      }
    }

    // Initial fetch and SSE connection
    loadRestData(true)
    connectSSE()

    // Background fallback polling (runs if SSE drops or for pagination)
    const timer = setInterval(() => {
      if (streamStatus !== 'LIVE') {
        loadRestData(false)
      }
    }, pollIntervalMs)

    return () => {
      mountedRef.current = false
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      clearInterval(timer)
    }
  }, [loadRestData, pollIntervalMs, streamStatus])

  const manualRefresh = useCallback(() => {
    return loadRestData(true)
  }, [loadRestData])

  return {
    status,
    market,
    indicators,
    currentSignal,
    signalsHistory,
    totalSignals,
    page,
    pageSize,
    setPage,
    setPageSize,
    isLoading,
    isRefreshing,
    lastUpdated,
    error,
    isOnline: streamStatus === 'LIVE' || status?.system_status === 'operational',
    streamStatus,
    refresh: manualRefresh,
  }
}
