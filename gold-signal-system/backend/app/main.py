"""
XAUUSD Gold Signal System — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, AsyncSessionLocal
from app.api.router import api_router

settings = get_settings()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Lazy import of scheduler (avoids import at module level for testability) ──
_scheduler = None


def _build_scheduler():
    """Construct the scheduler with its full dependency chain."""
    from app.market.xauusd_provider import get_market_provider
    from app.services.market_service import MarketService
    from app.services.signal_service import SignalService
    from app.services.scheduler import SignalScheduler

    provider = get_market_provider()
    market_svc = MarketService(provider=provider)
    signal_svc = SignalService()
    return SignalScheduler(
        market_service=market_svc,
        signal_service=signal_svc,
    )


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    logger.info("🚀  Starting %s v%s", settings.app_name, settings.app_version)
    await init_db()
    logger.info("✅  Database initialised")

    if settings.worker_enabled:
        _scheduler = _build_scheduler()
        app.state.scheduler = _scheduler
        await _scheduler.start(AsyncSessionLocal)
        logger.info("✅  Signal worker started")
    else:
        app.state.scheduler = None
        logger.info("⏸   Signal worker disabled (WORKER_ENABLED=false)")

    yield

    logger.info("🛑  Shutting down %s", settings.app_name)
    if _scheduler is not None:
        await _scheduler.stop()
    app.state.scheduler = None


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "ALERT-ONLY system that monitors XAUUSD, detects BUY/SELL signals "
        "from a Pine Script strategy, and sends Telegram alerts. "
        "This system NEVER places trades automatically."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.isdir(os.path.join(frontend_dist, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")


from fastapi import FastAPI, Request

@app.get("/", include_in_schema=False)
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/health",
        "status": "/api/status",
        "market": "/api/market",
        "signal": "/api/signal",
        "signals": "/api/signals",
        "settings": "/api/settings",
        "stream": "/api/stream",
    }


@app.get("/api", include_in_schema=False)
async def api_root():
    """Prevent 404 when browser or user hits /api directly."""
    return {
        "message": "XAUUSD Gold Signal System API",
        "version": settings.app_version,
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "status": "/api/status",
            "market": "/api/market",
            "indicators": "/api/indicators",
            "signal": "/api/signal",
            "signals": "/api/signals",
            "settings": "/api/settings",
            "stream": "/api/stream",
        },
    }
