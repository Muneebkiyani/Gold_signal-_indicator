import { useState } from 'react'
import { useTradingData } from './hooks/useTradingData'
import { Header } from './components/Header'
import type { ActivePage } from './components/Header'
import { SignalHeroCard } from './components/SignalHeroCard'
import { TrendCard } from './components/TrendCard'
import { MarketCardsGrid } from './components/MarketCardsGrid'
import { SignalHistoryTable } from './components/SignalHistoryTable'
import { SafetyBanner } from './components/SafetyBanner'
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
        <div className="ambient-glow" aria-hidden="true" />
        <Header
          status={status}
          streamStatus={streamStatus}
          isRefreshing={isRefreshing}
          lastUpdated={lastUpdated}
          onRefresh={refresh}
          activePage={activePage}
          onNavigate={setActivePage}
        />
        <main className="dashboard-content">
          <div className="loading-container">
            <div className="loading-spinner" aria-hidden="true" />
            <p className="loading-text">Connecting to XAUUSD Signal System...</p>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="trading-app">
      {/* Background ambient lighting */}
      <div className="ambient-glow" aria-hidden="true" />

      {/* Top Header with navigation */}
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
        <main className="dashboard-content" id="settings-main">
          <SettingsPage />
        </main>
      )}

      {/* ── Dashboard Page ────────────────────────────────────────────────── */}
      {activePage === 'dashboard' && (
        <main className="dashboard-content" id="dashboard-main">
          {/* Offline Warning if backend is not reachable */}
          {!isOnline && (
            <div className="offline-alert" role="alert">
              <span className="offline-icon">⚠️</span>
              <div className="offline-message">
                <strong>Backend Offline:</strong> Unable to connect to the FastAPI signal
                service at <code>http://localhost:8000/api</code>.
                {error && <span className="offline-detail"> ({error})</span>}
              </div>
              <button type="button" className="btn-retry" onClick={refresh}>
                Retry Connection
              </button>
            </div>
          )}

          {/* Hero Section: Active Signal + Trend Filter */}
          <div className="hero-signals-row">
            <SignalHeroCard
              currentSignal={currentSignal}
              currentPrice={market?.price ?? null}
            />
            <TrendCard
              trend={currentSignal?.trend ?? null}
              indicators={indicators}
            />
          </div>

          {/* Market Indicators Grid */}
          <MarketCardsGrid
            market={market}
            indicators={indicators}
          />

          {/* Signal History Table */}
          <SignalHistoryTable
            signals={signalsHistory}
            total={totalSignals}
            page={page}
            pageSize={pageSize}
            onPageChange={setPage}
          />

          {/* Mandatory Safety Notice */}
          <SafetyBanner />
        </main>
      )}

      {/* Trading Dashboard Footer */}
      <footer className="dashboard-footer">
        <div className="footer-left">
          <span>XAUUSD Gold Signal Alert System • v1.0.0</span>
          <span className="footer-separator">•</span>
          <span>Pine Script Rules (EMA 9/21, RSI 14, ADX 14, SMA 81)</span>
        </div>
        <div className="footer-right">
          <span>Informational only — No automated execution</span>
        </div>
      </footer>
    </div>
  )
}

export default App
