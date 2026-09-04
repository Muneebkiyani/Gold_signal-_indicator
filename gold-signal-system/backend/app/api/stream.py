"""
Server-Sent Events (SSE) stream endpoint — GET /api/stream
Pushes real-time market data, indicators, active signal, and alerts to the dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.market import _load_recent_candles
from app.config import get_settings
from app.crud.signal import get_latest_signal
from app.database import get_db
from app.services.broadcaster import get_broadcaster
from app.strategy.engine import IndicatorEngine

logger = logging.getLogger(__name__)
router = APIRouter()


async def _assemble_initial_snapshot(
    request: Request,
    session: AsyncSession,
) -> Dict[str, dict]:
    """Build the current state snapshot to immediately send to newly connected clients."""
    settings = get_settings()
    candles = await _load_recent_candles(request, session)

    # 1. Market quote
    latest_price = candles[-1].close if candles else None
    latest_ts = candles[-1].timestamp.isoformat() if candles else None
    market_data = {
        "symbol": settings.symbol,
        "timeframe": settings.timeframe,
        "price": latest_price,
        "timestamp": latest_ts,
    }

    # 2. Indicators
    if candles:
        engine = IndicatorEngine()
        vals = engine.calculate(candles)
        indicators_data = {
            "EMA9": vals.ema_fast,
            "EMA21": vals.ema_slow,
            "RSI": vals.rsi,
            "ADX": vals.adx,
            "DI+": vals.di_plus,
            "DI-": vals.di_minus,
            "SMA81": vals.sma_81,
            "ATR": vals.atr,
            "ema_fast": vals.ema_fast,
            "ema_slow": vals.ema_slow,
            "rsi": vals.rsi,
            "adx": vals.adx,
            "di_plus": vals.di_plus,
            "di_minus": vals.di_minus,
            "sma_81": vals.sma_81,
            "atr": vals.atr,
        }
    else:
        indicators_data = {}

    # 3. Active signal
    latest_sig = await get_latest_signal(
        session=session,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
    )
    if latest_sig:
        signal_data = {
            "signal": latest_sig.signal_type,
            "source": latest_sig.signal_source,
            "price": latest_sig.price,
            "candle_time": latest_sig.candle_time.isoformat(),
            "trend": latest_sig.trend,
        }
    else:
        signal_data = {
            "signal": "WAIT",
            "source": None,
            "price": latest_price,
            "candle_time": latest_ts,
            "trend": "FLAT",
        }

    # 4. Status
    scheduler = getattr(request.app.state, "scheduler", None)
    signal_engine_status = (
        "running"
        if scheduler and scheduler._task and not scheduler._task.done()
        else "idle"
    )
    telegram_status = (
        "enabled"
        if settings.telegram_enabled and settings.telegram_bot_token and settings.telegram_chat_id
        else "disabled"
    )

    status_data = {
        "system_status": "operational",
        "market_data_status": "connected" if candles else "ready",
        "database_status": "connected",
        "telegram_status": telegram_status,
        "signal_engine_status": signal_engine_status,
        "last_market_update": latest_ts,
        "last_processed_candle": latest_ts,
    }

    return {
        "snapshot": {
            "market": market_data,
            "indicators": indicators_data,
            "current_signal": signal_data,
            "status": status_data,
        }
    }


@router.get(
    "/stream",
    summary="Real-time Server-Sent Events Stream",
    description="Streams real-time price updates, indicators, signals, and system status via SSE.",
)
async def stream_events(
    request: Request,
    heartbeat: float = 15.0,
    max_events: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    broadcaster = get_broadcaster()
    initial_snapshot = await _assemble_initial_snapshot(request, session)

    async def event_generator():
        generator = broadcaster.subscribe(
            initial_data=initial_snapshot,
            heartbeat_interval=heartbeat,
            max_events=max_events,
        )
        try:
            async for chunk in generator:
                yield chunk
                if await request.is_disconnected():
                    break
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await generator.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
