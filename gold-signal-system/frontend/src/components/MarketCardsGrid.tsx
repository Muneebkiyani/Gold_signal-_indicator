import React from 'react'
import type { IndicatorsResponse, MarketResponse } from '../types/api'

interface MarketCardsGridProps {
  market: MarketResponse | null
  indicators: IndicatorsResponse | null
}

export const MarketCardsGrid: React.FC<MarketCardsGridProps> = ({
  market,
  indicators,
}) => {
  const price = market?.price ?? null
  const emaFast = indicators?.EMA9 ?? indicators?.ema_fast ?? null
  const emaSlow = indicators?.EMA21 ?? indicators?.ema_slow ?? null
  const rsi = indicators?.RSI ?? indicators?.rsi ?? null
  const adx = indicators?.ADX ?? indicators?.adx ?? null
  const diPlus = indicators?.['DI+'] ?? indicators?.di_plus ?? null
  const diMinus = indicators?.['DI-'] ?? indicators?.di_minus ?? null
  const sma81 = indicators?.SMA81 ?? indicators?.sma_81 ?? null
  const atr = indicators?.ATR ?? indicators?.atr ?? null

  const formatNumber = (val: number | null, decimals = 2): string => {
    if (val === null || val === undefined || isNaN(val)) return '—'
    return val.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  // EMA Difference
  const emaDiff = emaFast !== null && emaSlow !== null ? emaFast - emaSlow : null
  const isEmaBullish = emaDiff !== null && emaDiff > 0

  // RSI Percentage (clamped 0 - 100)
  const rsiPct = rsi !== null ? Math.min(100, Math.max(0, rsi)) : 50

  // ADX Percentage (clamped 0 - 60)
  const adxPct = adx !== null ? Math.min(100, (adx / 60) * 100) : 0

  // SMA 81 Distance
  const smaDiff = price !== null && sma81 !== null ? price - sma81 : null
  const isPriceAboveSma = smaDiff !== null && smaDiff > 0

  return (
    <section className="market-cards-section" aria-label="Strategy Indicators">
      <div className="section-header">
        <h2 className="section-title">STRATEGY INDICATORS</h2>
        <span className="section-subtitle">Parameters aligned with Pine Script (M15)</span>
      </div>

      <div className="market-grid-compact">
        {/* ── Card 1: EMA Crossover (9 & 21) ────────────────────────────── */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">EMA Trend (9 / 21)</span>
            <span className={`stat-badge ${isEmaBullish ? 'stat-badge-buy' : 'stat-badge-sell'}`}>
              {isEmaBullish ? 'Fast > Slow' : 'Fast < Slow'}
            </span>
          </div>

          <div className="ema-values-row">
            <div className="ema-val-col">
              <span className="ema-sub-label text-aqua">EMA 9 (Fast)</span>
              <span className="ema-val-number font-mono">{formatNumber(emaFast, 2)}</span>
            </div>
            <div className="ema-val-col">
              <span className="ema-sub-label text-orange">EMA 21 (Slow)</span>
              <span className="ema-val-number font-mono">{formatNumber(emaSlow, 2)}</span>
            </div>
          </div>

          <div className="stat-subtext">
            Spread: <strong className={isEmaBullish ? 'text-buy font-mono' : 'text-sell font-mono'}>
              {emaDiff !== null ? `${emaDiff >= 0 ? '+' : ''}${emaDiff.toFixed(2)}` : '—'}
            </strong>
          </div>
        </div>

        {/* ── Card 2: RSI Momentum (14) ─────────────────────────────────── */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">RSI Momentum (14)</span>
            <span
              className={`stat-badge ${
                rsi !== null && (rsi >= 70 || rsi <= 30)
                  ? 'stat-badge-warning'
                  : rsi !== null && rsi > 50
                  ? 'stat-badge-buy'
                  : 'stat-badge-sell'
              }`}
            >
              {rsi !== null
                ? rsi >= 70
                  ? 'Overbought (≥70)'
                  : rsi <= 30
                  ? 'Oversold (≤30)'
                  : rsi > 50
                  ? 'Bull Zone (50-70)'
                  : 'Bear Zone (30-50)'
                : '—'}
            </span>
          </div>

          <div className="stat-value font-mono">
            {rsi !== null ? rsi.toFixed(1) : '—'}
          </div>

          {/* Visual RSI Gauge */}
          <div className="rsi-gauge-wrap">
            <div className="rsi-gauge-bar">
              <div
                className="rsi-gauge-fill"
                style={{
                  width: `${rsiPct}%`,
                  background:
                    rsi !== null && rsi >= 70
                      ? '#ef4444'
                      : rsi !== null && rsi <= 30
                      ? '#f59e0b'
                      : rsi !== null && rsi > 50
                      ? '#10b981'
                      : '#38bdf8',
                }}
              />
              <span className="rsi-marker-30" title="Oversold (30)" />
              <span className="rsi-marker-50" title="Midline (50)" />
              <span className="rsi-marker-70" title="Overbought (70)" />
            </div>
            <div className="rsi-scale-labels">
              <span>30</span>
              <span>50 Mid</span>
              <span>70</span>
            </div>
          </div>
        </div>

        {/* ── Card 3: ADX & DMI (14) ────────────────────────────────────── */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">ADX Trend Strength (14)</span>
            <span
              className={`stat-badge ${
                adx !== null && adx >= 20 ? 'stat-badge-buy' : 'stat-badge-neutral'
              }`}
            >
              {adx !== null && adx >= 20 ? 'Strong Trend (≥20)' : 'Weak / Choppy (<20)'}
            </span>
          </div>

          <div className="stat-value font-mono">
            {adx !== null ? adx.toFixed(1) : '—'}
          </div>

          {/* Visual ADX Meter */}
          <div className="rsi-gauge-wrap">
            <div className="rsi-gauge-bar">
              <div
                className="rsi-gauge-fill"
                style={{
                  width: `${adxPct}%`,
                  background: adx !== null && adx >= 20 ? '#10b981' : '#64748b',
                }}
              />
              <span className="rsi-marker-30" style={{ left: '33.3%' }} title="Min Trend Threshold (20)" />
            </div>
            <div className="rsi-scale-labels">
              <span>0</span>
              <span>20 Min Trend</span>
              <span>60+</span>
            </div>
          </div>

          {/* DI+ vs DI- meter */}
          <div className="di-metrics-row">
            <div className="di-metric">
              <span className="di-label text-buy">DI+ (Bull):</span>
              <span className="di-val font-mono">{formatNumber(diPlus, 1)}</span>
            </div>
            <div className="di-metric">
              <span className="di-label text-sell">DI- (Bear):</span>
              <span className="di-val font-mono">{formatNumber(diMinus, 1)}</span>
            </div>
          </div>
        </div>

        {/* ── Card 4: SMA 81 Trend (Script 2) ──────────────────────────── */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">SMA 81 Crossover</span>
            <span className={`stat-badge ${isPriceAboveSma ? 'stat-badge-buy' : 'stat-badge-sell'}`}>
              {isPriceAboveSma ? 'Price > SMA 81' : 'Price < SMA 81'}
            </span>
          </div>

          <div className="stat-value font-mono text-orange">
            {sma81 !== null ? `$${formatNumber(sma81, 2)}` : '—'}
          </div>

          <div className="stat-subtext">
            Distance:{' '}
            <strong className={isPriceAboveSma ? 'text-buy font-mono' : 'text-sell font-mono'}>
              {smaDiff !== null ? `${smaDiff >= 0 ? '+' : ''}$${smaDiff.toFixed(2)}` : '—'}
            </strong>{' '}
            ({isPriceAboveSma ? 'Bullish bias' : 'Bearish bias'})
          </div>
        </div>

        {/* ── Card 5: ATR Volatility (14) ───────────────────────────────── */}
        <div className="stat-card stat-card-compact">
          <div className="stat-card-header">
            <span className="stat-name">ATR Volatility (14)</span>
            <span className="stat-badge stat-badge-gold">Bar Range</span>
          </div>

          <div className="stat-value font-mono text-gold">
            {atr !== null ? `$${formatNumber(atr, 2)}` : '—'}
          </div>

          <div className="stat-subtext">Average true range per 15m candle</div>
        </div>
      </div>
    </section>
  )
}
