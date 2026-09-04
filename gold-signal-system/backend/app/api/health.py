"""Health check endpoint — GET /api/health"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()
settings = get_settings()

_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    timestamp: str
    uptime_seconds: float


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the current health status of the API server.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(time.time() - _start_time, 2),
    )
