/**
 * TypeScript API contracts matching the backend FastAPI schemas.
 */

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error'
  app: string
  version: string
  timestamp: string
  uptime_seconds: number
}

export interface StatusResponse {
  system_status: string
  market_data_status: string
  database_status: string
  telegram_status: string
  signal_engine_status: string
  last_market_update: string | null
  last_processed_candle: string | null
}

export interface MarketResponse {
  symbol: string
  timeframe: string
  price: number | null
  timestamp: string | null
}

export interface IndicatorsResponse {
  EMA9?: number | null
  EMA21?: number | null
  RSI?: number | null
  ADX?: number | null
  'DI+'?: number | null
  'DI-'?: number | null
  SMA81?: number | null
  ATR?: number | null
  ema_fast?: number | null
  ema_slow?: number | null
  rsi?: number | null
  adx?: number | null
  di_plus?: number | null
  di_minus?: number | null
  sma_81?: number | null
  atr?: number | null
}

export type SignalType = 'BUY' | 'SELL' | 'WAIT' | 'NO_ENTRY'
export type TrendDirection = 'UP' | 'DOWN' | 'FLAT' | 'WEAK'

export interface SignalCurrentResponse {
  signal: SignalType | string
  source: string | null
  price: number | null
  candle_time: string | null
  trend: TrendDirection | string | null
}

export interface SignalRecord {
  id?: number
  symbol: string
  timeframe: string
  signal_type: SignalType | string
  signal_source: string
  candle_time: string
  price: number
  ema_fast?: number | null
  ema_slow?: number | null
  rsi?: number | null
  adx?: number | null
  di_plus?: number | null
  di_minus?: number | null
  sma_81?: number | null
  atr?: number | null
  trend?: TrendDirection | string | null
  telegram_sent: boolean
  telegram_attempts: number
  telegram_last_attempt?: string | null
  telegram_error?: string | null
  created_at?: string | null
}

export interface SignalListResponse {
  items: SignalRecord[]
  total: number
  limit: number
  offset: number
}

export interface SettingsResponse {
  app_name: string
  app_version: string
  debug: boolean
  log_level: string
  host: string
  port: number
  allowed_origins: string
  symbol: string
  timeframe: string
  ema_fast: number
  ema_slow: number
  rsi_length: number
  rsi_mid: number
  rsi_overbought: number
  rsi_oversold: number
  adx_length: number
  adx_smoothing: number
  adx_min: number
  sma_length: number
  atr_length: number
  signal_on_close: boolean
  worker_enabled: boolean
  poll_interval_seconds: number
  candle_history_limit: number
  telegram_enabled: boolean
  no_entry_telegram_alerts: boolean
}

export interface StreamPayload {
  market?: MarketResponse
  indicators?: IndicatorsResponse
  current_signal?: SignalCurrentResponse
  status?: StatusResponse
  new_signals?: SignalRecord[]
}

export interface StreamMessage {
  type: 'snapshot' | 'tick' | 'signal' | string
  timestamp: string
  payload: StreamPayload
}

export interface UpdateSettingsRequest {
  symbol?: string
  timeframe?: string
  ema_fast?: number
  ema_slow?: number
  rsi_length?: number
  rsi_mid?: number
  rsi_overbought?: number
  rsi_oversold?: number
  adx_length?: number
  adx_smoothing?: number
  adx_min?: number
  sma_length?: number
  atr_length?: number
  signal_on_close?: boolean
  telegram_enabled?: boolean
  no_entry_telegram_alerts?: boolean
  poll_interval_seconds?: number
  candle_history_limit?: number
  worker_enabled?: boolean
}
