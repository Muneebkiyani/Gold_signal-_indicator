import React from 'react'
import type { SignalRecord } from '../types/api'

interface SignalHistoryTableProps {
  signals: SignalRecord[]
  total: number
  page: number
  pageSize: number
  onPageChange: (newPage: number) => void
}

export const SignalHistoryTable: React.FC<SignalHistoryTableProps> = ({
  signals,
  total,
  page,
  pageSize,
  onPageChange,
}) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  const formatSignalBadge = (sigType: string) => {
    const s = sigType.toUpperCase()
    if (s === 'BUY') {
      return <span className="table-badge badge-buy">BUY</span>
    }
    if (s === 'SELL') {
      return <span className="table-badge badge-sell">SELL</span>
    }
    if (s === 'NO_ENTRY' || s === 'NO ENTRY') {
      return <span className="table-badge badge-noentry">NO ENTRY</span>
    }
    return <span className="table-badge badge-wait">WAIT</span>
  }

  const formatSource = (source: string) => {
    if (source === 'EMA_RSI_ADX') return 'EMA+RSI+ADX'
    if (source === 'SMA_81') return 'SMA 81'
    return source
  }

  const formatTelegramStatus = (sig: SignalRecord) => {
    if (sig.telegram_sent) {
      return (
        <span className="tg-pill tg-sent" title="Alert delivered to Telegram channel">
          ✓ Sent
        </span>
      )
    }
    if (sig.telegram_attempts > 0) {
      return (
        <span
          className="tg-pill tg-failed"
          title={`Failed after ${sig.telegram_attempts} attempts: ${sig.telegram_error || 'Network error'}`}
        >
          ✕ Failed
        </span>
      )
    }
    return (
      <span className="tg-pill tg-pending" title="Alert pending or suppressed (NO_ENTRY/WAIT)">
        —
      </span>
    )
  }

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString)
      return d.toLocaleString('en-US', {
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    } catch {
      return isoString
    }
  }

  return (
    <section className="signal-history-section" aria-label="Signal History">
      <div className="section-header table-section-header">
        <div>
          <h2 className="section-title">SIGNAL HISTORY</h2>
          <span className="section-subtitle">
            Audited Trading Signals ({total} total recorded events)
          </span>
        </div>

        <div className="table-pagination-meta">
          <span>
            Page {page + 1} of {totalPages}
          </span>
        </div>
      </div>

      <div className="table-container">
        <table className="signals-table">
          <thead>
            <tr>
              <th>Time (UTC)</th>
              <th>Symbol</th>
              <th>TF</th>
              <th>Signal</th>
              <th>Source</th>
              <th>Price</th>
              <th>RSI</th>
              <th>ADX</th>
              <th>Trend</th>
              <th>Telegram</th>
            </tr>
          </thead>
          <tbody>
            {signals.length === 0 ? (
              <tr>
                <td colSpan={10} className="table-empty">
                  No signals recorded yet. Worker is listening for completed M15 candle closes.
                </td>
              </tr>
            ) : (
              signals.map((sig, idx) => (
                <tr key={sig.id || `${sig.candle_time}-${idx}`}>
                  <td className="font-mono">{formatTime(sig.candle_time)}</td>
                  <td className="font-mono text-gold">{sig.symbol}</td>
                  <td className="font-mono">{sig.timeframe}</td>
                  <td>{formatSignalBadge(sig.signal_type)}</td>
                  <td className="font-mono text-secondary">{formatSource(sig.signal_source)}</td>
                  <td className="font-mono font-semibold">
                    ${sig.price.toFixed(2)}
                  </td>
                  <td className="font-mono">
                    {sig.rsi !== null && sig.rsi !== undefined ? sig.rsi.toFixed(1) : '—'}
                  </td>
                  <td className="font-mono">
                    {sig.adx !== null && sig.adx !== undefined ? sig.adx.toFixed(1) : '—'}
                  </td>
                  <td>
                    <span className={`trend-tag trend-tag-${(sig.trend || 'flat').toLowerCase()}`}>
                      {sig.trend || '—'}
                    </span>
                  </td>
                  <td>{formatTelegramStatus(sig)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Bar */}
      <div className="pagination-bar">
        <button
          type="button"
          className="btn-page"
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0}
        >
          ← Previous
        </button>
        <span className="page-indicator">
          Showing {signals.length > 0 ? page * pageSize + 1 : 0} –{' '}
          {Math.min(total, (page + 1) * pageSize)} of {total}
        </span>
        <button
          type="button"
          className="btn-page"
          onClick={() => onPageChange(page + 1)}
          disabled={page + 1 >= totalPages}
        >
          Next →
        </button>
      </div>
    </section>
  )
}
