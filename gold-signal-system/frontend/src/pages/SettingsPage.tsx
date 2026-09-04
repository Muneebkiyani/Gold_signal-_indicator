/**
 * SettingsPage — Strategy & system configuration panel.
 *
 * Rules enforced here:
 *  - AUTOMATIC TRADING is permanently DISABLED and cannot be enabled.
 *  - Private credentials (token, chat ID, API key) are never shown.
 *  - All changes are validated client-side before being sent to the backend.
 */

import { useCallback, useEffect, useState } from 'react'
import type { SettingsResponse, UpdateSettingsRequest } from '../types/api'
import { useSettings } from '../hooks/useSettings'

// ── Sub-components ────────────────────────────────────────────────────────────

interface NumberFieldProps {
  id: string
  label: string
  hint?: string
  value: number
  min?: number
  max?: number
  step?: number
  onChange: (v: number) => void
}

function NumberField({
  id,
  label,
  hint,
  value,
  min,
  max,
  step = 1,
  onChange,
}: NumberFieldProps) {
  const [raw, setRaw] = useState(String(value))

  useEffect(() => {
    setRaw(String(value))
  }, [value])

  const commit = () => {
    const n = Number(raw)
    if (!isNaN(n)) onChange(n)
    else setRaw(String(value))
  }

  return (
    <div className="settings-field">
      <label className="settings-label" htmlFor={id}>
        {label}
      </label>
      {hint && <span className="settings-hint">{hint}</span>}
      <input
        id={id}
        type="number"
        className="settings-input"
        value={raw}
        min={min}
        max={max}
        step={step}
        onChange={(e) => setRaw(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && commit()}
      />
    </div>
  )
}

interface ToggleFieldProps {
  id: string
  label: string
  hint?: string
  checked: boolean
  onChange: (v: boolean) => void
}

function ToggleField({ id, label, hint, checked, onChange }: ToggleFieldProps) {
  return (
    <div className="settings-field settings-field-toggle">
      <div className="settings-toggle-text">
        <label className="settings-label" htmlFor={id}>
          {label}
        </label>
        {hint && <span className="settings-hint">{hint}</span>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        className={`settings-toggle ${checked ? 'settings-toggle-on' : 'settings-toggle-off'}`}
        onClick={() => onChange(!checked)}
      >
        <span className="settings-toggle-thumb" />
      </button>
    </div>
  )
}

interface SelectFieldProps {
  id: string
  label: string
  hint?: string
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}

function SelectField({ id, label, hint, value, options, onChange }: SelectFieldProps) {
  return (
    <div className="settings-field">
      <label className="settings-label" htmlFor={id}>
        {label}
      </label>
      {hint && <span className="settings-hint">{hint}</span>}
      <select
        id={id}
        className="settings-input settings-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}

interface TextFieldProps {
  id: string
  label: string
  hint?: string
  value: string
  onChange: (v: string) => void
}

function TextField({ id, label, hint, value, onChange }: TextFieldProps) {
  return (
    <div className="settings-field">
      <label className="settings-label" htmlFor={id}>
        {label}
      </label>
      {hint && <span className="settings-hint">{hint}</span>}
      <input
        id={id}
        type="text"
        className="settings-input"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        spellCheck={false}
        autoComplete="off"
      />
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const TIMEFRAME_OPTIONS = [
  { value: 'M1', label: 'M1 — 1 Minute' },
  { value: 'M5', label: 'M5 — 5 Minutes' },
  { value: 'M15', label: 'M15 — 15 Minutes' },
  { value: 'M30', label: 'M30 — 30 Minutes' },
  { value: 'H1', label: 'H1 — 1 Hour' },
  { value: 'H4', label: 'H4 — 4 Hours' },
  { value: 'D1', label: 'D1 — Daily' },
]

export function SettingsPage() {
  const { settings, isLoading, isSaving, error, successMessage, save, reset } =
    useSettings()

  // Local draft state — initialized from server settings once loaded
  const [draft, setDraft] = useState<Partial<SettingsResponse>>({})

  useEffect(() => {
    if (settings && Object.keys(draft).length === 0) {
      setDraft({ ...settings })
    }
  }, [settings, draft])

  const set = useCallback(
    <K extends keyof SettingsResponse>(key: K, value: SettingsResponse[K]) => {
      setDraft((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  const handleSave = async () => {
    if (!settings) return
    // Only send fields that differ from current server state
    const patch: UpdateSettingsRequest = {}
    const keys = Object.keys(draft) as (keyof SettingsResponse)[]
    for (const key of keys) {
      const draftVal = draft[key]
      const serverVal = settings[key]
      if (draftVal !== serverVal) {
        ;(patch as Record<string, unknown>)[key] = draftVal
      }
    }
    await save(patch)
  }

  const handleReset = async () => {
    setDraft({})
    await reset()
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="settings-page">
        <div className="settings-loading">
          <div className="loading-spinner" aria-hidden="true" />
          <p className="loading-text">Loading settings…</p>
        </div>
      </div>
    )
  }

  const d = draft as SettingsResponse

  return (
    <div className="settings-page">
      {/* ── Page title ───────────────────────────────────────────────────── */}
      <div className="settings-page-header">
        <div>
          <h1 className="settings-page-title">System Settings</h1>
          <p className="settings-page-subtitle">
            Configure strategy parameters. Changes apply to the next signal evaluation.
          </p>
        </div>
      </div>

      {/* ── AUTOMATIC TRADING DISABLED banner ───────────────────────────── */}
      <div className="settings-trading-disabled-banner" role="alert" aria-live="polite">
        <div className="settings-disabled-icon" aria-hidden="true">🔒</div>
        <div className="settings-disabled-body">
          <div className="settings-disabled-title">AUTOMATIC TRADING — DISABLED</div>
          <div className="settings-disabled-text">
            This system is a <strong>signal alert tool only</strong>. It does not execute
            trades, connect to brokers, or manage any account. Automatic trading cannot be
            enabled from this dashboard.
          </div>
        </div>
        <div className="settings-disabled-badge">INFORMATIONAL ONLY</div>
      </div>

      {/* ── Feedback banners ─────────────────────────────────────────────── */}
      {error && (
        <div className="settings-feedback settings-feedback-error" role="alert">
          <span className="settings-feedback-icon">⚠</span>
          <span>{error}</span>
        </div>
      )}
      {successMessage && (
        <div className="settings-feedback settings-feedback-success" role="status">
          <span className="settings-feedback-icon">✓</span>
          <span>{successMessage}</span>
        </div>
      )}

      <div className="settings-grid">
        {/* ── Section 1: Instrument ──────────────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">📊</span>
            <div>
              <h2 className="settings-section-title">Instrument</h2>
              <p className="settings-section-desc">Trading symbol and chart timeframe</p>
            </div>
          </div>
          <div className="settings-fields-row">
            <TextField
              id="setting-symbol"
              label="Symbol"
              hint="e.g. XAUUSD, EURUSD"
              value={d.symbol ?? 'XAUUSD'}
              onChange={(v) => set('symbol', v)}
            />
            <SelectField
              id="setting-timeframe"
              label="Timeframe"
              hint="Chart bar period"
              value={d.timeframe ?? 'M15'}
              options={TIMEFRAME_OPTIONS}
              onChange={(v) => set('timeframe', v)}
            />
          </div>
        </section>

        {/* ── Section 2: EMA ────────────────────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">📈</span>
            <div>
              <h2 className="settings-section-title">EMA Settings</h2>
              <p className="settings-section-desc">
                Exponential Moving Average crossover periods
              </p>
            </div>
          </div>
          <div className="settings-fields-row">
            <NumberField
              id="setting-ema-fast"
              label="EMA Fast"
              hint="Must be less than EMA Slow"
              value={d.ema_fast ?? 9}
              min={1}
              max={499}
              onChange={(v) => set('ema_fast', v)}
            />
            <NumberField
              id="setting-ema-slow"
              label="EMA Slow"
              hint="Must be greater than EMA Fast"
              value={d.ema_slow ?? 21}
              min={2}
              max={500}
              onChange={(v) => set('ema_slow', v)}
            />
          </div>
          {(d.ema_fast ?? 9) >= (d.ema_slow ?? 21) && (
            <p className="settings-inline-error">
              ⚠ EMA Fast must be strictly less than EMA Slow
            </p>
          )}
        </section>

        {/* ── Section 3: RSI ────────────────────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">🔄</span>
            <div>
              <h2 className="settings-section-title">RSI Settings</h2>
              <p className="settings-section-desc">
                Relative Strength Index thresholds
              </p>
            </div>
          </div>
          <div className="settings-fields-row settings-fields-row-4">
            <NumberField
              id="setting-rsi-length"
              label="RSI Length"
              hint="Lookback period"
              value={d.rsi_length ?? 14}
              min={2}
              max={500}
              onChange={(v) => set('rsi_length', v)}
            />
            <NumberField
              id="setting-rsi-mid"
              label="RSI Midline"
              hint="Trend bias threshold"
              value={d.rsi_mid ?? 50}
              min={0}
              max={100}
              step={0.5}
              onChange={(v) => set('rsi_mid', v)}
            />
            <NumberField
              id="setting-rsi-overbought"
              label="Overbought"
              hint="Upper signal level"
              value={d.rsi_overbought ?? 70}
              min={50}
              max={100}
              step={0.5}
              onChange={(v) => set('rsi_overbought', v)}
            />
            <NumberField
              id="setting-rsi-oversold"
              label="Oversold"
              hint="Lower signal level"
              value={d.rsi_oversold ?? 30}
              min={0}
              max={50}
              step={0.5}
              onChange={(v) => set('rsi_oversold', v)}
            />
          </div>
          {(d.rsi_oversold ?? 30) >= (d.rsi_overbought ?? 70) && (
            <p className="settings-inline-error">
              ⚠ RSI Oversold must be strictly less than RSI Overbought
            </p>
          )}
        </section>

        {/* ── Section 4: ADX ────────────────────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">💪</span>
            <div>
              <h2 className="settings-section-title">ADX Settings</h2>
              <p className="settings-section-desc">
                Average Directional Index — trend strength filter
              </p>
            </div>
          </div>
          <div className="settings-fields-row settings-fields-row-3">
            <NumberField
              id="setting-adx-length"
              label="ADX Length"
              hint="DI calculation period"
              value={d.adx_length ?? 14}
              min={1}
              max={500}
              onChange={(v) => set('adx_length', v)}
            />
            <NumberField
              id="setting-adx-smoothing"
              label="ADX Smoothing"
              hint="Wilder smoothing period"
              value={d.adx_smoothing ?? 14}
              min={1}
              max={500}
              onChange={(v) => set('adx_smoothing', v)}
            />
            <NumberField
              id="setting-adx-min"
              label="Minimum ADX"
              hint="Required trend strength"
              value={d.adx_min ?? 20}
              min={0}
              max={100}
              step={0.5}
              onChange={(v) => set('adx_min', v)}
            />
          </div>
        </section>

        {/* ── Section 5: Moving Averages ────────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">📉</span>
            <div>
              <h2 className="settings-section-title">Moving Averages</h2>
              <p className="settings-section-desc">
                SMA trend bias filter and ATR volatility
              </p>
            </div>
          </div>
          <div className="settings-fields-row">
            <NumberField
              id="setting-sma-length"
              label="SMA Length"
              hint="Trend bias SMA period"
              value={d.sma_length ?? 81}
              min={1}
              max={1000}
              onChange={(v) => set('sma_length', v)}
            />
            <NumberField
              id="setting-atr-length"
              label="ATR Length"
              hint="Volatility / SL sizing period"
              value={d.atr_length ?? 14}
              min={1}
              max={500}
              onChange={(v) => set('atr_length', v)}
            />
          </div>
        </section>

        {/* ── Section 6: Signal Behaviour ───────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">🎯</span>
            <div>
              <h2 className="settings-section-title">Signal Behaviour</h2>
              <p className="settings-section-desc">
                When and how signals are generated
              </p>
            </div>
          </div>
          <div className="settings-fields-column">
            <ToggleField
              id="setting-signal-on-close"
              label="Signal on Close"
              hint="Generate signals only on confirmed bar close (recommended)"
              checked={d.signal_on_close ?? true}
              onChange={(v) => set('signal_on_close', v)}
            />
          </div>
        </section>

        {/* ── Section 7: Telegram Alerts ────────────────────────────────── */}
        <section className="settings-section">
          <div className="settings-section-header">
            <span className="settings-section-icon">📬</span>
            <div>
              <h2 className="settings-section-title">Telegram Alerts</h2>
              <p className="settings-section-desc">
                Push alerts to your Telegram bot — credentials configured in .env only
              </p>
            </div>
          </div>
          <div className="settings-fields-column">
            <ToggleField
              id="setting-telegram-enabled"
              label="Telegram Alerts"
              hint="Send BUY / SELL alerts via Telegram"
              checked={d.telegram_enabled ?? false}
              onChange={(v) => set('telegram_enabled', v)}
            />
            <ToggleField
              id="setting-no-entry-alerts"
              label="No-Entry Alerts"
              hint="Also send NO_ENTRY / WAIT messages to Telegram"
              checked={d.no_entry_telegram_alerts ?? false}
              onChange={(v) => set('no_entry_telegram_alerts', v)}
            />
          </div>
          <div className="settings-credential-note">
            <span className="settings-credential-icon">🔐</span>
            Telegram Bot Token and Chat ID are configured in the server{' '}
            <code>.env</code> file and are never exposed here.
          </div>
        </section>
      </div>

      {/* ── Action Bar ───────────────────────────────────────────────────── */}
      <div className="settings-action-bar">
        <button
          type="button"
          id="settings-reset-btn"
          className="settings-btn settings-btn-ghost"
          onClick={handleReset}
          disabled={isSaving}
        >
          Reset to Saved
        </button>
        <button
          type="button"
          id="settings-save-btn"
          className="settings-btn settings-btn-primary"
          onClick={handleSave}
          disabled={isSaving || !settings}
          aria-busy={isSaving}
        >
          {isSaving ? (
            <>
              <span className="settings-spinner" aria-hidden="true" />
              Saving…
            </>
          ) : (
            'Save Settings'
          )}
        </button>
      </div>
    </div>
  )
}
