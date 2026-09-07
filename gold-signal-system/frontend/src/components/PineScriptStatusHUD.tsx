import React from 'react'
import type { IndicatorsResponse, SignalCurrentResponse } from '../types/api'
import type { NextSignalCountdown } from '../hooks/useNextSignalCountdown'

interface PineScriptStatusHUDProps {
  currentSignal: SignalCurrentResponse | null
  indicators: IndicatorsResponse | null
  countdown?: NextSignalCountdown
}

export const PineScriptStatusHUD: React.FC<PineScriptStatusHUDProps> = ({
  currentSignal,
  indicators,
  countdown,
}) => {
  const adxVal = indicators?.ADX ?? indicators?.adx ?? null
  const rsiVal = indicators?.RSI ?? indicators?.rsi ?? null
  const diPlus = indicators?.['DI+'] ?? indicators?.di_plus ?? null
  const diMinus = indicators?.['DI-'] ?? indicators?.di_minus ?? null

  // Pine Script Logic:
  // trendStrongUp   = adxVal > 20 and diPlus > diMinus
  // trendStrongDown = adxVal > 20 and diMinus > diPlus
  // trendText = trendStrongUp ? "UP" : trendStrongDown ? "DOWN" : "WEAK"
  let trendText = 'WEAK'
  if (adxVal !== null && diPlus !== null && diMinus !== null && adxVal > 20) {
    if (diPlus > diMinus) trendText = 'UP'
    else if (diMinus > diPlus) trendText = 'DOWN'
  }

  // weakTrend    = adxVal < 20
  // rsiExtreme   = rsiVal >= 70 or rsiVal <= 30
  // noEntryZone  = weakTrend or rsiExtreme
  const isWeakTrend = adxVal !== null && adxVal < 20
  const isRsiExtreme = rsiVal !== null && (rsiVal >= 70 || rsiVal <= 30)
  const isNoEntry = isWeakTrend || isRsiExtreme

  // statusText = buySignal ? "BUY" : sellSignal ? "SELL" : noEntryZone ? "NO ENTRY" : "WAIT"
  const rawSig = (currentSignal?.signal || '').toUpperCase()
  let statusText = 'WAIT'
  let statusTheme = 'hud-wait'

  if (rawSig === 'BUY') {
    statusText = 'BUY'
    statusTheme = 'hud-buy'
  } else if (rawSig === 'SELL') {
    statusText = 'SELL'
    statusTheme = 'hud-sell'
  } else if (isNoEntry || rawSig === 'NO_ENTRY') {
    statusText = 'NO ENTRY'
    statusTheme = 'hud-noentry'
  }

  return (
    <div className="pine-hud-card">
      <div className="pine-hud-header">
        <div className="pine-hud-title-wrap">
          <span className="pine-script-badge">Pine Script v5</span>
          <span className="pine-hud-title">LIVE STRATEGY MATRIX</span>
        </div>
        <div className="pine-hud-header-right">
          {countdown && (
            <div className="pine-next-bar-badge font-mono" title={`Target: ${countdown.formattedTargetTime}`}>
              <span className="mini-clock-label">Next Bar:</span>
              <span className="mini-clock-val text-gold">{countdown.formattedTime}</span>
            </div>
          )}
          <div className={`pine-zone-pill ${isNoEntry ? 'zone-noentry' : 'zone-active'}`}>
            <span className="zone-dot" />
            {isNoEntry ? (
              <span>
                NO ENTRY: {isWeakTrend && isRsiExtreme ? 'Choppy + RSI Extreme' : isWeakTrend ? 'Choppy (ADX < 20)' : 'RSI Exhaustion'}
              </span>
            ) : (
              <span>CLEAR TRADING ZONE</span>
            )}
          </div>
        </div>
      </div>

      {/* Replicating TradingView statusTable (4 columns) */}
      <div className="pine-hud-grid">
        {/* Cell 1: Signal */}
        <div className={`pine-hud-cell ${statusTheme}`}>
          <span className="hud-cell-label">Signal</span>
          <span className="hud-cell-val font-mono">{statusText}</span>
        </div>

        {/* Cell 2: Trend */}
        <div className={`pine-hud-cell trend-${trendText.toLowerCase()}`}>
          <span className="hud-cell-label">Trend</span>
          <span className="hud-cell-val font-mono">
            {trendText === 'UP' && '▲ UP'}
            {trendText === 'DOWN' && '▼ DOWN'}
            {trendText === 'WEAK' && '● WEAK'}
          </span>
        </div>

        {/* Cell 3: ADX */}
        <div className="pine-hud-cell">
          <span className="hud-cell-label">ADX (14)</span>
          <span className="hud-cell-val font-mono">
            {adxVal !== null ? adxVal.toFixed(1) : '—'}
          </span>
          <span className="hud-cell-sub">
            {adxVal !== null && adxVal >= 20 ? 'Strong ≥ 20' : 'Weak < 20'}
          </span>
        </div>

        {/* Cell 4: RSI */}
        <div className="pine-hud-cell">
          <span className="hud-cell-label">RSI (14)</span>
          <span className="hud-cell-val font-mono">
            {rsiVal !== null ? rsiVal.toFixed(1) : '—'}
          </span>
          <span className="hud-cell-sub">
            {rsiVal !== null
              ? rsiVal >= 70
                ? 'Overbought'
                : rsiVal <= 30
                ? 'Oversold'
                : rsiVal > 50
                ? 'Bull Zone (50-70)'
                : 'Bear Zone (30-50)'
              : '—'}
          </span>
        </div>
      </div>
    </div>
  )
}
