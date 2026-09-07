import React from 'react'
import type { SignalCurrentResponse, IndicatorsResponse } from '../types/api'

interface SignalHeroCardProps {
  currentSignal: SignalCurrentResponse | null
  currentPrice: number | null
  indicators: IndicatorsResponse | null
}

export const SignalHeroCard: React.FC<SignalHeroCardProps> = ({
  currentSignal,
  currentPrice,
  indicators,
}) => {
  const signalType = (currentSignal?.signal || 'WAIT').toUpperCase()
  const priceVal = currentSignal?.price ?? currentPrice
  const candleTime = currentSignal?.candle_time
    ? new Date(currentSignal.candle_time).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
      })
    : 'Waiting for bar close'

  const emaFast = indicators?.EMA9 ?? indicators?.ema_fast ?? null
  const emaSlow = indicators?.EMA21 ?? indicators?.ema_slow ?? null
  const rsi = indicators?.RSI ?? indicators?.rsi ?? null
  const adx = indicators?.ADX ?? indicators?.adx ?? null
  const diPlus = indicators?.['DI+'] ?? indicators?.di_plus ?? null
  const diMinus = indicators?.['DI-'] ?? indicators?.di_minus ?? null
  const sma81 = indicators?.SMA81 ?? indicators?.sma_81 ?? null

  const getSignalMeta = () => {
    switch (signalType) {
      case 'BUY':
        return {
          cardClass: 'signal-card-buy',
          badgeClass: 'badge-buy',
          icon: '🟢',
          title: 'BUY SIGNAL',
          subtext: 'EMA 9 Crossed Above EMA 21 • Bullish RSI • ADX Confirmed',
        }
      case 'SELL':
        return {
          cardClass: 'signal-card-sell',
          badgeClass: 'badge-sell',
          icon: '🔴',
          title: 'SELL SIGNAL',
          subtext: 'EMA 9 Crossed Below EMA 21 • Bearish RSI • ADX Confirmed',
        }
      case 'NO_ENTRY':
      case 'NO ENTRY':
        return {
          cardClass: 'signal-card-noentry',
          badgeClass: 'badge-noentry',
          icon: '⚠️',
          title: 'NO ENTRY',
          subtext: 'Choppy Market Condition (ADX < 20) or RSI Exhaustion (≥70 / ≤30)',
        }
      case 'WAIT':
      default:
        return {
          cardClass: 'signal-card-wait',
          badgeClass: 'badge-wait',
          icon: '⏳',
          title: 'WAIT',
          subtext: 'Scanning M15 bar close for confirmed EMA/RSI/ADX crossover setup',
        }
    }
  }

  const meta = getSignalMeta()

  return (
    <section className={`hero-signal-card ${meta.cardClass}`} aria-label="Current Signal">
      <div className="hero-card-glow" aria-hidden="true" />

      <div className="hero-top-row">
        <div className="hero-signal-left">
          <span className="hero-badge-tag">ACTIVE M15 SIGNAL</span>
          <div className={`signal-hero-pill ${meta.badgeClass}`}>
            <span className="signal-icon">{meta.icon}</span>
            <span className="signal-text">{meta.title}</span>
          </div>
        </div>

        <div className="hero-price-wrap">
          <span className="hero-price-caption">Live Spot Price (XAUUSD)</span>
          <div className="hero-price-val font-mono">
            {priceVal !== null && priceVal !== undefined
              ? `$${priceVal.toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}`
              : '—'}
          </div>
        </div>
      </div>

      <p className="hero-signal-desc">{meta.subtext}</p>

      {/* Conditions Checklist based on Pine Script rules */}
      <div className="hero-conditions-row">
        {/* 1. EMA 9 vs 21 */}
        <div className="hero-condition-item">
          <span className="condition-name">EMA 9 / 21:</span>
          {emaFast !== null && emaSlow !== null ? (
            <span className={`condition-val ${emaFast > emaSlow ? 'text-buy' : 'text-sell'}`}>
              {emaFast > emaSlow ? '▲ Bullish (9 > 21)' : '▼ Bearish (9 < 21)'}
            </span>
          ) : (
            <span className="condition-val text-muted">—</span>
          )}
        </div>

        {/* 2. RSI Zone */}
        <div className="hero-condition-item">
          <span className="condition-name">RSI Zone:</span>
          {rsi !== null ? (
            <span
              className={`condition-val ${
                rsi >= 70 || rsi <= 30
                  ? 'text-warning'
                  : rsi > 50
                  ? 'text-buy'
                  : 'text-sell'
              }`}
            >
              {rsi >= 70
                ? 'Overbought (≥70)'
                : rsi <= 30
                ? 'Oversold (≤30)'
                : rsi > 50
                ? 'Bull Zone (50-70)'
                : 'Bear Zone (30-50)'}
            </span>
          ) : (
            <span className="condition-val text-muted">—</span>
          )}
        </div>

        {/* 3. ADX & Trend */}
        <div className="hero-condition-item">
          <span className="condition-name">ADX Trend:</span>
          {adx !== null && diPlus !== null && diMinus !== null ? (
            <span className={`condition-val ${adx >= 20 ? (diPlus > diMinus ? 'text-buy' : 'text-sell') : 'text-muted'}`}>
              {adx >= 20
                ? diPlus > diMinus
                  ? `Strong Up (ADX ${adx.toFixed(1)})`
                  : `Strong Down (ADX ${adx.toFixed(1)})`
                : `Weak / Choppy (${adx.toFixed(1)} < 20)`}
            </span>
          ) : (
            <span className="condition-val text-muted">—</span>
          )}
        </div>

        {/* 4. SMA 81 Filter */}
        <div className="hero-condition-item">
          <span className="condition-name">SMA 81 Bias:</span>
          {priceVal !== null && sma81 !== null ? (
            <span className={`condition-val ${priceVal > sma81 ? 'text-buy' : 'text-sell'}`}>
              {priceVal > sma81 ? 'Bullish (Price > SMA)' : 'Bearish (Price < SMA)'}
            </span>
          ) : (
            <span className="condition-val text-muted">—</span>
          )}
        </div>

        {/* Bar Timestamp */}
        <div className="hero-condition-item candle-time-item">
          <span className="condition-name">Bar Close:</span>
          <span className="condition-val font-mono">{candleTime}</span>
        </div>
      </div>
    </section>
  )
}
