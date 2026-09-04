"""API router — aggregates all sub-routers under /api prefix."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.settings import router as settings_router
from app.api.signals import router as signals_router
from app.api.status import router as status_router
from app.api.stream import router as stream_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(status_router, tags=["Status"])
api_router.include_router(market_router, tags=["Market & Indicators"])
api_router.include_router(signals_router, tags=["Signals"])
api_router.include_router(settings_router, tags=["Settings"])
api_router.include_router(stream_router, tags=["Stream"])
