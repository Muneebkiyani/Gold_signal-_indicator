import React from 'react'
import type { SignalCurrentResponse } from '../types/api'

interface SignalHeroCardProps {
  currentSignal: SignalCurrentResponse | null
  currentPrice: number | null
}

export const SignalHeroCard: React.FC<SignalHeroCardProps> = ({
  currentSignal,
  currentPrice,
}) => {
  const signalType = (currentSignal?.signal || 'WAIT').toUpperCase()
  const sourceRaw = currentSignal?.source || 'Strategy Pipeline'
  const sourceLabel =
    sourceRaw === 'EMA_RSI_ADX'
      ? 'EMA + RSI + ADX'
      : sourceRaw === 'SMA_81'
      ? 'SMA 81 Crossover'
      : sourceRaw

  const priceVal = currentSignal?.price ?? currentPrice
  const candleTime = currentSignal?.candle_time
    ? new Date(currentSignal.candle_time).toUTCString().replace('GMT', 'UTC')
    : 'Waiting for candle close...'

  const trendVal = (currentSignal?.trend || 'FLAT').toUpperCase()

  // Visual classes per signal type
  const getSignalMeta = () => {
    switch (signalType) {
      case 'BUY':
        return {
          cardClass: 'signal-card-buy',
          badgeClass: 'badge-buy',
          icon: '🟢',
          title: 'BUY SIGNAL',
          subtext: 'Bullish Momentum & Trend Filter Confirmed',
        }
      case 'SELL':
        return {
          cardClass: 'signal-card-sell',
          badgeClass: 'badge-sell',
          icon: '🔴',
          title: 'SELL SIGNAL',
          subtext: 'Bearish Momentum & Trend Filter Confirmed',
        }
      case 'NO_ENTRY':
      case 'NO ENTRY':
        return {
          cardClass: 'signal-card-noentry',
          badgeClass: 'badge-noentry',
          icon: '⚠️',
          title: 'NO ENTRY',
          subtext: 'Disqualified Zone — Weak Trend (ADX < 20) or Extreme RSI',
        }
      case 'WAIT':
      default:
        return {
          cardClass: 'signal-card-wait',
          badgeClass: 'badge-wait',
          icon: '⏳',
          title: 'WAIT',
          subtext: 'Monitoring M15 Candle Boundaries for Setup Conditions',
        }
    }
  }

  const meta = getSignalMeta()

  return (
    <section className={`hero-signal-card ${meta.cardClass}`} aria-label="Current Signal Evaluation">
      <div className="hero-card-glow" aria-hidden="true" />

      <div className="hero-card-header">
        <div className="hero-signal-status">
          <span className="hero-badge-tag">ACTIVE SIGNAL</span>
          <div className={`signal-hero-pill ${meta.badgeClass}`}>
            <span className="signal-icon">{meta.icon}</span>
            <span className="signal-text">{meta.title}</span>
          </div>
        </div>

        <div className="hero-trend-badge">
          <span className="trend-label">Trend Filter</span>
          <span className={`trend-pill trend-${trendVal.toLowerCase()}`}>
            {trendVal === 'UP' && '▲ UP'}
            {trendVal === 'DOWN' && '▼ DOWN'}
            {trendVal === 'WEAK' && '● WEAK'}
            {trendVal === 'FLAT' && '— FLAT'}
          </span>
        </div>
      </div>

      <div className="hero-card-body">
        <div className="hero-price-display">
          <span className="hero-price-label">Signal / Close Price</span>
          <div className="hero-price-value font-mono">
            {priceVal !== null && priceVal !== undefined
              ? `$${priceVal.toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}`
              : '—'}
          </div>
          <p className="hero-subtitle">{meta.subtext}</p>
        </div>

        <div className="hero-meta-grid">
          <div className="meta-cell">
            <span className="meta-cell-label">Signal Source</span>
            <span className="meta-cell-value font-mono text-gold">{sourceLabel}</span>
          </div>

          <div className="meta-cell">
            <span className="meta-cell-label">Timeframe</span>
            <span className="meta-cell-value font-mono">XAUUSD • M15</span>
          </div>

          <div className="meta-cell meta-cell-wide">
            <span className="meta-cell-label">Trigger Candle Bar (UTC)</span>
            <span className="meta-cell-value font-mono meta-time">{candleTime}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
