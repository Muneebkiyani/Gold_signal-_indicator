import { useState } from 'react'
import { useTradingData } from './hooks/useTradingData'
import { Header } from './components/Header'
import type { ActivePage } from './components/Header'
import { SignalHeroCard } from './components/SignalHeroCard'
import { PineScriptStatusHUD } from './components/PineScriptStatusHUD'
import { MarketCardsGrid } from './components/MarketCardsGrid'
import { SignalHistoryTable } from './components/SignalHistoryTable'
import { SettingsPage } from './pages/SettingsPage'
import './App.css'

function App() {
  const [activePage, setActivePage] = useState<ActivePage>('dashboard')

  const {
    status,
    market,
    indicators,
    currentSignal,
    signalsHistory,
    totalSignals,
    page,
    pageSize,
    setPage,
    isLoading,
    isRefreshing,
    lastUpdated,
    error,
    isOnline,
    streamStatus,
    refresh,
  } = useTradingData(6000)

  // ── Loading skeleton (only on initial load, not on page switch) ────────────
  if (isLoading && !status && !market) {
    return (
      <div className="trading-app">
        <div className="loading-screen" role="status" aria-label="Loading Gold Signal System">
          <div className="loading-spinner" />
          <p className="loading-text">CONNECTING TO GOLD MARKET DATA...</p>
          <span className="loading-subtext">Initializing Pine Script Strategy & Indicators</span>
        </div>
      </div>
    )
  }

  return (
    <div className="trading-app">
      {/* Background ambient lighting */}
      <div className="ambient-glow" aria-hidden="true" />

      {/* Main Header & Navigation */}
      <Header
        status={status}
        streamStatus={streamStatus}
        isRefreshing={isRefreshing}
        lastUpdated={lastUpdated}
        onRefresh={refresh}
        activePage={activePage}
        onNavigate={setActivePage}
      />

      {/* ── Settings Page ─────────────────────────────────────────────────── */}
      {activePage === 'settings' && (
        <SettingsPage />
      )}

      {/* ── Dashboard Page ────────────────────────────────────────────────── */}
      {activePage === 'dashboard' && (
        <main className="dashboard-content" id="dashboard-main">
          {/* Offline alert (only if backend unreachable) */}
          {!isOnline && (
            <div className="offline-alert" role="alert">
              <span className="offline-icon">⚠️</span>
              <div className="offline-message">
                <strong>Backend Offline:</strong> Unable to reach signal service at{' '}
                <code>http://localhost:8000/api</code>.
                {error && <span className="offline-detail"> ({error})</span>}
              </div>
              <button type="button" className="btn-retry" onClick={refresh}>
                Retry
              </button>
            </div>
          )}

          {/* Section 1: Hero Signal Command Center + Pine Script HUD */}
          <div className="hero-signals-row">
            <SignalHeroCard
              currentSignal={currentSignal}
              currentPrice={market?.price ?? null}
              indicators={indicators}
            />
            <PineScriptStatusHUD
              currentSignal={currentSignal}
              indicators={indicators}
            />
          </div>

          {/* Section 2: Core Pine Script Indicator Metrics */}
          <MarketCardsGrid
            market={market}
            indicators={indicators}
          />

          {/* Section 3: Verified Signals Log */}
          <SignalHistoryTable
            signals={signalsHistory}
            total={totalSignals}
            page={page}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </main>
      )}

      {/* Streamlined Trading Footer */}
      <footer className="dashboard-footer">
        <div className="footer-left">
          <span>XAUUSD Gold Signal System • M15 Strategy</span>
          <span className="footer-separator">•</span>
          <span>Pine Script Rules (EMA 9/21, RSI 14, ADX 14, SMA 81)</span>
        </div>
        <div className="footer-right">
          <span>Manual execution only — Alerts dispatched via Telegram</span>
        </div>
      </footer>
    </div>
  )
}

export default App
