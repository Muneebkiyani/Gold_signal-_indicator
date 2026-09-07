import React from 'react'
import type { StatusResponse } from '../types/api'
import type { StreamConnectionStatus } from '../hooks/useTradingData'

export type ActivePage = 'dashboard' | 'settings'

interface HeaderProps {
  status: StatusResponse | null
  streamStatus: StreamConnectionStatus
  isRefreshing: boolean
  lastUpdated: Date | null
  onRefresh: () => void
  activePage: ActivePage
  onNavigate: (page: ActivePage) => void
}

export const Header: React.FC<HeaderProps> = ({
  status,
  streamStatus,
  isRefreshing,
  lastUpdated,
  onRefresh,
  activePage,
  onNavigate,
}) => {
  const getMarketStatusBadge = () => {
    const raw = status?.market_data_status || ''
    const isClosed = raw.toLowerCase().includes('closed')
    if (isClosed) {
      return (
        <div className="status-pill status-pill-warning" title={raw}>
          <span className="dot dot-warning" />
          <span>Market: Closed (Weekend)</span>
        </div>
      )
    }
    return (
      <div className="status-pill status-pill-success" title="Spot Gold interbank market is open">
        <span className="dot dot-success" />
        <span>Market: Open</span>
      </div>
    )
  }

  const getTelegramStatusBadge = () => {
    const tg = status?.telegram_status
    if (tg === 'enabled') {
      return (
        <div className="status-pill status-pill-success" title="Telegram alerts active and bot connected">
          <span className="dot dot-success" />
          <span>Telegram: Connected</span>
        </div>
      )
    }
    if (tg === 'misconfigured') {
      return (
        <div className="status-pill status-pill-error" title="Telegram bot token or chat ID missing">
          <span className="dot dot-error" />
          <span>Telegram: Error</span>
        </div>
      )
    }
    return (
      <div className="status-pill status-pill-neutral" title="Telegram alerts disabled in settings">
        <span className="dot dot-neutral" />
        <span>Telegram: Disconnected</span>
      </div>
    )
  }

  const getStreamBadge = () => {
    if (streamStatus === 'LIVE') {
      return (
        <div className="status-pill status-pill-live" title="Real-time Server-Sent Events (SSE) active">
          <span className="dot dot-live" />
          <span className="status-label">LIVE</span>
        </div>
      )
    }
    if (streamStatus === 'RECONNECTING') {
      return (
        <div className="status-pill status-pill-reconnecting" title="Connection interrupted, reconnecting...">
          <span className="dot dot-reconnecting" />
          <span className="status-label">RECONNECTING</span>
        </div>
      )
    }
    return (
      <div className="status-pill status-pill-offline" title="Backend service offline">
        <span className="dot dot-offline" />
        <span className="status-label">OFFLINE</span>
      </div>
    )
  }

  return (
    <header className="dashboard-header">
      <div className="header-left">
        <div className="brand-badge">
          <span className="gold-au">Au</span>
        </div>
        <div className="brand-info">
          <h1 className="brand-title">
            GOLD SIGNAL <span className="text-gold">SYSTEM</span>
          </h1>
          <div className="instrument-tags">
            <span className="instrument-badge">XAUUSD</span>
            <span className="timeframe-badge">M15</span>
            <span className="system-pill">Pine Script Engine</span>
          </div>
        </div>
      </div>

      {/* ── Navigation tabs ─────────────────────────────────────────────── */}
      <nav className="header-nav" aria-label="Main navigation">
        <button
          type="button"
          id="nav-dashboard"
          className={`header-nav-btn ${activePage === 'dashboard' ? 'header-nav-btn-active' : ''}`}
          onClick={() => onNavigate('dashboard')}
          aria-current={activePage === 'dashboard' ? 'page' : undefined}
        >
          <svg
            className="header-nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          Dashboard
        </button>
        <button
          type="button"
          id="nav-settings"
          className={`header-nav-btn ${activePage === 'settings' ? 'header-nav-btn-active' : ''}`}
          onClick={() => onNavigate('settings')}
          aria-current={activePage === 'settings' ? 'page' : undefined}
        >
          <svg
            className="header-nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          Settings
        </button>
      </nav>

      <div className="header-right">
        {/* Market Hours Status */}
        {getMarketStatusBadge()}

        {/* Telegram Status */}
        {getTelegramStatusBadge()}

        {/* Live Streaming Status (LIVE / RECONNECTING / OFFLINE) */}
        {getStreamBadge()}

        {/* Refresh & Time */}
        <div className="refresh-container">
          <button
            type="button"
            className={`btn-refresh ${isRefreshing ? 'is-spinning' : ''}`}
            onClick={onRefresh}
            title="Refresh dashboard data"
            aria-label="Refresh data"
          >
            <svg
              className="icon-refresh"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
          </button>
          {lastUpdated && (
            <span className="time-caption" title="Last successful update">
              {lastUpdated.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
