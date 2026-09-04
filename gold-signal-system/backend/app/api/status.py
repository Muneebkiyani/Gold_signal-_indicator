"""
Status endpoint — GET /api/status
Provides real-time system, database, market data, and alert engine status.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import StatusResponse
from app.config import get_settings
from app.crud.candle import get_latest_candle
from app.database import get_db
from app.services.scheduler import SignalScheduler

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_scheduler(request: Request) -> Optional[SignalScheduler]:
    return getattr(request.app.state, "scheduler", None)


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="System Status",
    description="Returns real-time status of system, database, market data, and Telegram alerts.",
)
async def get_status(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> StatusResponse:
    settings = get_settings()
    scheduler = _get_scheduler(request)

    # 1. Database Connectivity Check
    db_status = "connected"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database status check failed: %s", exc)
        db_status = "error"

    # 2. Telegram Alert Status
    if not settings.telegram_enabled:
        telegram_status = "disabled"
    elif settings.telegram_bot_token and settings.telegram_chat_id:
        telegram_status = "enabled"
    else:
        telegram_status = "misconfigured"

    # 3. Scheduler & Signal Engine Status
    signal_engine_status = "idle"
    market_data_status = "ready"
    last_processed_candle = None
    last_market_update = None

    if scheduler is not None:
        if scheduler._task is not None and not scheduler._task.done():
            signal_engine_status = "running"
            market_data_status = "connected"
        else:
            signal_engine_status = "stopped"

        # Check engine memory state
        engine = scheduler._signal_service._engine
        if engine.last_evaluated_candle_time is not None:
            last_processed_candle = engine.last_evaluated_candle_time
        if engine.candle_manager.last_processed_candle_time is not None:
            last_market_update = engine.candle_manager.last_processed_candle_time

    # Fallback to database latest candle if not present in memory
    if last_market_update is None or last_processed_candle is None:
        latest_db_candle = await get_latest_candle(
            session=session,
            symbol=settings.symbol,
            timeframe=settings.timeframe,
        )
        if latest_db_candle is not None:
            if last_market_update is None:
                last_market_update = latest_db_candle.timestamp
            if last_processed_candle is None:
                last_processed_candle = latest_db_candle.timestamp

    # Overall system status
    system_status = "operational" if db_status == "connected" else "degraded"

    return StatusResponse(
        system_status=system_status,
        market_data_status=market_data_status,
        database_status=db_status,
        telegram_status=telegram_status,
        signal_engine_status=signal_engine_status,
        last_market_update=last_market_update,
        last_processed_candle=last_processed_candle,
    )
