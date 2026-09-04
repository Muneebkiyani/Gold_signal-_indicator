/**
 * API service layer — wraps fetch calls to the FastAPI backend.
 * Base URL is resolved via Vite proxy (/api → http://localhost:8000/api)
 * or the VITE_API_URL env variable for production deployments.
 */

import type {
  HealthResponse,
  IndicatorsResponse,
  MarketResponse,
  SettingsResponse,
  SignalCurrentResponse,
  SignalListResponse,
  SignalRecord,
  StatusResponse,
  UpdateSettingsRequest,
} from '../types/api'

const rawBase = import.meta.env.VITE_API_URL?.trim()
const apiHost = rawBase
  ? (rawBase.startsWith('http') ? rawBase : `https://${rawBase}`).replace(/\/+$/, '')
  : ''
const API_BASE = apiHost ? `${apiHost}/api` : '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: 'application/json',
    },
  })
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const fetchHealth = (): Promise<HealthResponse> =>
  get<HealthResponse>('/health')

export const fetchStatus = (): Promise<StatusResponse> =>
  get<StatusResponse>('/status')

export const fetchMarket = (): Promise<MarketResponse> =>
  get<MarketResponse>('/market')

export const fetchIndicators = (): Promise<IndicatorsResponse> =>
  get<IndicatorsResponse>('/indicators')

export const fetchCurrentSignal = (): Promise<SignalCurrentResponse> =>
  get<SignalCurrentResponse>('/signal')

export const fetchSignals = (
  limit = 20,
  offset = 0,
  signalType?: string,
  signalSource?: string
): Promise<SignalListResponse> => {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  if (signalType) params.set('signal_type', signalType)
  if (signalSource) params.set('signal_source', signalSource)

  return get<SignalListResponse>(`/signals?${params.toString()}`)
}

export const fetchLatestSignal = (): Promise<SignalRecord> =>
  get<SignalRecord>('/signals/latest')

export const fetchSettings = (): Promise<SettingsResponse> =>
  get<SettingsResponse>('/settings')

export const updateSettings = (
  payload: UpdateSettingsRequest
): Promise<SettingsResponse> => {
  const API_BASE_URL = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api`
    : '/api'
  return fetch(`${API_BASE_URL}/settings`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      const detail =
        typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail ?? body)
      throw new Error(detail || `HTTP ${res.status}`)
    }
    return res.json() as Promise<SettingsResponse>
  })
}
