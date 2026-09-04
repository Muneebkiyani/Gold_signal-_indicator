# Documentation

## Phase 1 — Scaffolding (Current)

- FastAPI backend with health endpoint
- React + TypeScript frontend init screen
- SQLite database (async via aiosqlite)
- Full project structure ready for Phase 2

## Phase 2 — Market Data (Next)

Will implement:
- XAUUSD OHLCV data fetching from a market data provider
- Candle models and database storage
- Background polling loop
- `/api/market/status` and `/api/candles` endpoints

## Phase 3 — Strategy Engine

Will implement:
- Pine Script strategy reproduction in Python
- EMA crossover + RSI signal detection
- BUY/SELL signal generation
- Signal history storage

## Phase 4 — Telegram Alerts

Will implement:
- Telegram Bot API integration
- Alert formatting with entry price, SL, TP
- Alert history log

## Phase 5 — Full Dashboard

Will implement:
- Candlestick chart with signal overlays
- Live price ticker
- Signal history table
- Alert log
- System status panel
