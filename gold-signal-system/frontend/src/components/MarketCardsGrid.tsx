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

  // RSI status badge
  const getRsiStatus = (val: number | null) => {
    if (val === null) return { text: 'Neutral', cls: 'pill-neutral' }
    if (val >= 70) return { text: 'Overbought (≥70)', cls: 'pill-sell' }
    if (val <= 30) return { text: 'Oversold (≤30)', cls: 'pill-buy' }
    if (val > 50) return { text: 'Bullish Zone (>50)', cls: 'pill-buy-muted' }
    return { text: 'Bearish Zone (<50)', cls: 'pill-sell-muted' }
  }

  // ADX status
  const getAdxStatus = (val: number | null) => {
    if (val === null) return { text: '—', cls: 'pill-neutral' }
    if (val > 20) return { text: 'Strong Trend (>20)', cls: 'pill-buy' }
    return { text: 'Weak Trend (≤20)', cls: 'pill-warning' }
  }

  // EMA cross status
  const getEmaComparison = () => {
    if (emaFast === null || emaSlow === null) return null
    if (emaFast > emaSlow) {
      return { text: 'Fast > Slow (Bullish)', cls: 'text-buy' }
    }
    if (emaFast < emaSlow) {
      return { text: 'Fast < Slow (Bearish)', cls: 'text-sell' }
    }
    return { text: 'Equal', cls: 'text-muted' }
  }

  const emaComp = getEmaComparison()
  const rsiMeta = getRsiStatus(rsi)
  const adxMeta = getAdxStatus(adx)

  return (
    <section className="market-cards-section" aria-label="Technical Indicators">
      <div className="section-header">
        <h2 className="section-title">MARKET INDICATORS</h2>
        <span className="section-subtitle">Real-time M15 Candle Strategy Metrics</span>
      </div>

      <div className="market-grid">
        {/* 1. Current Price */}
        <div className="stat-card stat-card-highlight">
          <div className="stat-card-header">
            <span className="stat-name">XAUUSD Price</span>
            <span className="stat-badge stat-badge-gold">Live Spot</span>
          </div>
          <div className="stat-value font-mono text-gold">
            {price !== null ? `$${formatNumber(price, 2)}` : '—'}
          </div>
          <div className="stat-subtext">Gold spot quote (15-min bar)</div>
        </div>

        {/* 2. EMA 9 */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">EMA 9</span>
            <span className="stat-badge">Fast Trend</span>
          </div>
          <div className="stat-value font-mono">
            {emaFast !== null ? formatNumber(emaFast, 2) : '—'}
          </div>
          <div className="stat-subtext">
            {emaComp ? (
              <span className={emaComp.cls}>{emaComp.text}</span>
            ) : (
              '9-period exponential average'
            )}
          </div>
        </div>

        {/* 3. EMA 21 */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">EMA 21</span>
            <span className="stat-badge">Slow Trend</span>
          </div>
          <div className="stat-value font-mono">
            {emaSlow !== null ? formatNumber(emaSlow, 2) : '—'}
          </div>
          <div className="stat-subtext">21-period exponential average</div>
        </div>

        {/* 4. RSI (14) */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">RSI 14</span>
            <span className={`stat-badge ${rsiMeta.cls}`}>{rsiMeta.text}</span>
          </div>
          <div className="stat-value font-mono">
            {rsi !== null ? formatNumber(rsi, 2) : '—'}
          </div>
          <div className="stat-progress-bar">
            <div
              className="stat-progress-fill"
              style={{ width: `${Math.min(100, Math.max(0, rsi || 0))}%` }}
            />
          </div>
        </div>

        {/* 5. ADX (14) */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">ADX 14</span>
            <span className={`stat-badge ${adxMeta.cls}`}>{adxMeta.text}</span>
          </div>
          <div className="stat-value font-mono">
            {adx !== null ? formatNumber(adx, 2) : '—'}
          </div>
          <div className="stat-subtext">Directional strength (Threshold &gt; 20)</div>
        </div>

        {/* 6. DI+ */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">DI+</span>
            <span className="stat-badge pill-buy-muted">+ Directional</span>
          </div>
          <div className="stat-value font-mono text-buy">
            {diPlus !== null ? formatNumber(diPlus, 2) : '—'}
          </div>
          <div className="stat-subtext">Positive directional movement</div>
        </div>

        {/* 7. DI- */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">DI-</span>
            <span className="stat-badge pill-sell-muted">- Directional</span>
          </div>
          <div className="stat-value font-mono text-sell">
            {diMinus !== null ? formatNumber(diMinus, 2) : '—'}
          </div>
          <div className="stat-subtext">Negative directional movement</div>
        </div>

        {/* 8. SMA 81 */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">SMA 81</span>
            <span className="stat-badge">Macro Filter</span>
          </div>
          <div className="stat-value font-mono">
            {sma81 !== null ? formatNumber(sma81, 2) : '—'}
          </div>
          <div className="stat-subtext">81-period baseline moving average</div>
        </div>

        {/* 9. ATR 14 */}
        <div className="stat-card">
          <div className="stat-card-header">
            <span className="stat-name">ATR 14</span>
            <span className="stat-badge">Volatility</span>
          </div>
          <div className="stat-value font-mono">
            {atr !== null ? `$${formatNumber(atr, 2)}` : '—'}
          </div>
          <div className="stat-subtext">Average True Range (Risk / SL sizing)</div>
        </div>
      </div>
    </section>
  )
}
