# XAUUSD Gold Signal System — Backend

FastAPI backend for the XAUUSD Gold Signal Alert System.

> ⚠️ **ALERT-ONLY system. No automatic trading.**

## Quick Start

```bash
cd backend

# 1. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env as needed (defaults work for local dev)

# 4. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root — links to docs and health |
| GET | `/api/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

## Project Structure

```
app/
├── main.py        — FastAPI app, lifespan, CORS
├── config.py      — Pydantic settings (reads .env)
├── database.py    — Async SQLite engine + session
├── api/           — HTTP route handlers
│   ├── router.py  — Central router
│   └── health.py  — GET /api/health
├── market/        — (Phase 2) Market data fetching
├── strategy/      — (Phase 2) Pine Script strategy logic
├── alerts/        — (Phase 3) Telegram alert dispatcher
├── services/      — Shared business-logic services
└── models/        — SQLModel database models
```

## Running Tests

```bash
pytest tests/ -v
```

## Phase Roadmap

| Phase | Feature |
|-------|---------|
| 1 ✅ | Project scaffolding, health endpoint |
| 2 | Market data integration (XAUUSD OHLCV) |
| 3 | Pine Script strategy engine (BUY/SELL signals) |
| 4 | Telegram alert dispatcher |
| 5 | Full web dashboard |
