# XAUUSD Gold Signal System

> ⚠️ **ALERT-ONLY system. This system NEVER places trades automatically.**

Real-time XAUUSD Gold signal alert system that monitors price action, reproduces a Pine Script strategy, detects BUY/SELL signals, and sends Telegram alerts — all displayed on a live web dashboard.

## Architecture

```
gold-signal-system/
├── backend/          — FastAPI + SQLite signal engine
├── frontend/         — React + TypeScript dashboard
├── data/             — SQLite database (auto-created)
├── docs/             — Project documentation
└── docker-compose.yml
```

## Quick Start

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs  
Health: http://localhost:8000/api/health

### Frontend

> Requires Node.js 18+. Install from https://nodejs.org

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Dashboard: http://localhost:5173

## Phase Roadmap

| Phase | Status | Feature |
|-------|--------|---------|
| 1 | ✅ Complete | Project scaffolding, health endpoint, React init screen |
| 2 | ⏳ Next | Market data integration — live XAUUSD OHLCV |
| 3 | ⏳ Future | Pine Script strategy engine — BUY/SELL signal detection |
| 4 | ⏳ Future | Telegram alert dispatcher |
| 5 | ⏳ Future | Full live dashboard — charts, signals, history |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLModel, SQLite, httpx |
| Frontend | React 18, TypeScript, Vite |
| Alerts | Telegram Bot API (Phase 4) |
| Infra | Docker Compose |

## Testing the Health Endpoint

```bash
# curl
curl http://localhost:8000/api/health

# Expected response
{
  "status": "ok",
  "app": "XAUUSD Gold Signal System",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00+00:00",
  "uptime_seconds": 12.34
}
```

## License

Private — do not distribute.
