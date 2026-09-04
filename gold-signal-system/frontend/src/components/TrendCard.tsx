import React from 'react'
import type { IndicatorsResponse, TrendDirection } from '../types/api'

interface TrendCardProps {
  trend: TrendDirection | string | null
  indicators: IndicatorsResponse | null
}

export const TrendCard: React.FC<TrendCardProps> = ({ trend, indicators }) => {
  const trendNormalized = (trend || 'WEAK').toUpperCase()
  const adxVal = indicators?.ADX ?? indicators?.adx ?? null
  const diPlus = indicators?.['DI+'] ?? indicators?.di_plus ?? null
  const diMinus = indicators?.['DI-'] ?? indicators?.di_minus ?? null

  const getTrendData = () => {
    switch (trendNormalized) {
      case 'UP':
        return {
          label: 'BULLISH UPTREND',
          status: 'UP',
          icon: '▲',
          colorClass: 'trend-bullish',
          desc: 'Strong upward momentum (ADX > 20 and DI+ > DI-)',
        }
      case 'DOWN':
        return {
          label: 'BEARISH DOWNTREND',
          status: 'DOWN',
          icon: '▼',
          colorClass: 'trend-bearish',
          desc: 'Strong downward momentum (ADX > 20 and DI- > DI+)',
        }
      case 'WEAK':
      case 'FLAT':
      default:
        return {
          label: 'WEAK / RANGING',
          status: 'WEAK',
          icon: '●',
          colorClass: 'trend-weak',
          desc: 'Indecisive or choppy market (ADX <= 20). NO ENTRY zone.',
        }
    }
  }

  const data = getTrendData()

  return (
    <div className={`trend-card ${data.colorClass}`}>
      <div className="trend-card-header">
        <span className="card-caption">MARKET TREND BIAS</span>
        <span className="trend-pill-badge">{data.status}</span>
      </div>

      <div className="trend-card-main">
        <div className="trend-indicator-symbol" aria-hidden="true">
          {data.icon}
        </div>
        <div className="trend-details">
          <h3 className="trend-title">{data.label}</h3>
          <p className="trend-desc">{data.desc}</p>
        </div>
      </div>

      <div className="trend-metrics">
        <div className="trend-metric-item">
          <span className="metric-label">ADX (14)</span>
          <span className="metric-val font-mono">
            {adxVal !== null ? adxVal.toFixed(2) : '—'}
          </span>
        </div>
        <div className="trend-metric-item">
          <span className="metric-label">DI+</span>
          <span className="metric-val font-mono text-buy">
            {diPlus !== null ? diPlus.toFixed(2) : '—'}
          </span>
        </div>
        <div className="trend-metric-item">
          <span className="metric-label">DI-</span>
          <span className="metric-val font-mono text-sell">
            {diMinus !== null ? diMinus.toFixed(2) : '—'}
          </span>
        </div>
      </div>
    </div>
  )
}
