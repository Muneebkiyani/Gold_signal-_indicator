"""
Market and Indicators endpoints — GET /api/market, GET /api/indicators
Provides real-time market data and technical indicator snapshots.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import IndicatorsResponse, MarketResponse
from app.config import get_settings
from app.crud.candle import get_candles, get_latest_candle
from app.database import get_db
from app.market.models import NormalizedCandle
from app.services.scheduler import SignalScheduler
from app.strategy.engine import IndicatorEngine

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_scheduler(request: Request) -> Optional[SignalScheduler]:
    return getattr(request.app.state, "scheduler", None)


async def _load_recent_candles(
    request: Request,
    session: AsyncSession,
) -> List[NormalizedCandle]:
    """Retrieve the current candle history from worker memory or database."""
    settings = get_settings()
    scheduler = _get_scheduler(request)

    # 1. Try memory cache from running worker
    if scheduler is not None:
        engine = scheduler._signal_service._engine
        if engine.candle_manager.candles:
            return list(engine.candle_manager.candles)

    # 2. Fall back to database
    db_candles = await get_candles(
        session=session,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
        limit=settings.candle_history_limit,
        ascending=True,
    )

    return [
        NormalizedCandle(
            timestamp=c.timestamp,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
        )
        for c in db_candles
    ]


@router.get(
    "/market",
    response_model=MarketResponse,
    summary="Current Market Quote",
    description="Returns the current trading symbol, timeframe, latest price, and timestamp.",
)
async def get_market(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> MarketResponse:
    settings = get_settings()
    candles = await _load_recent_candles(request, session)

    if candles:
        latest = candles[-1]
        return MarketResponse(
            symbol=settings.symbol,
            timeframe=settings.timeframe,
            price=latest.close,
            timestamp=latest.timestamp,
        )

    # If no candles yet in memory or DB
    db_latest = await get_latest_candle(
        session=session,
        symbol=settings.symbol,
        timeframe=settings.timeframe,
    )
    if db_latest is not None:
        return MarketResponse(
            symbol=db_latest.symbol,
            timeframe=db_latest.timeframe,
            price=db_latest.close,
            timestamp=db_latest.timestamp,
        )

    return MarketResponse(
        symbol=settings.symbol,
        timeframe=settings.timeframe,
        price=None,
        timestamp=None,
    )


@router.get(
    "/indicators",
    response_model=IndicatorsResponse,
    summary="Technical Indicators Snapshot",
    description="Returns latest EMA 9, EMA 21, RSI, ADX, DI+, DI-, SMA 81, and ATR values.",
)
async def get_indicators(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> IndicatorsResponse:
    candles = await _load_recent_candles(request, session)

    if not candles:
        return IndicatorsResponse()

    engine = IndicatorEngine()
    vals = engine.calculate(candles)

    return IndicatorsResponse(
        EMA9=vals.ema_fast,
        EMA21=vals.ema_slow,
        RSI=vals.rsi,
        ADX=vals.adx,
        DI_plus=vals.di_plus,
        DI_minus=vals.di_minus,
        SMA81=vals.sma_81,
        ATR=vals.atr,
        ema_fast=vals.ema_fast,
        ema_slow=vals.ema_slow,
        rsi=vals.rsi,
        adx=vals.adx,
        di_plus=vals.di_plus,
        di_minus=vals.di_minus,
        sma_81=vals.sma_81,
        atr=vals.atr,
    )


# ── MT5 Live Data Integration Endpoints ───────────────────────────────────────

from datetime import datetime
from pydantic import BaseModel, Field


class MT5CandleIn(BaseModel):
    symbol: str = Field("XAUUSD", description="Symbol e.g. XAUUSD")
    timeframe: str = Field("M15", description="Timeframe e.g. M15")
    timestamp: datetime = Field(..., description="Candle open timestamp (ISO or UTC)")
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class MT5HistoryIn(BaseModel):
    symbol: str = Field("XAUUSD", description="Symbol e.g. XAUUSD")
    timeframe: str = Field("M15", description="Timeframe e.g. M15")
    candles: List[MT5CandleIn]


@router.post(
    "/market/candle",
    summary="Push live candle from MT5",
    description="Receives completed candles directly from MetaTrader 5 Expert Advisor.",
)
async def push_mt5_candle(
    candle_in: MT5CandleIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    scheduler = _get_scheduler(request)

    normalized = NormalizedCandle(
        timestamp=candle_in.timestamp,
        open=candle_in.open,
        high=candle_in.high,
        low=candle_in.low,
        close=candle_in.close,
        volume=candle_in.volume,
    )

    signals_generated = []
    signal_svc = scheduler._signal_service if scheduler is not None else getattr(request.app.state, "signal_service", None)
    if signal_svc is None:
        from app.services.signal_service import SignalService
        signal_svc = SignalService()
        await signal_svc.initialize(session)
        request.app.state.signal_service = signal_svc

    signals_generated = await signal_svc.evaluate([normalized], session)

    try:
        from app.services.broadcaster import get_broadcaster

        broadcaster = get_broadcaster()
        engine = IndicatorEngine()
        history = signal_svc._engine.candle_manager.candles
        vals = engine.calculate(history) if history else None

        payload = {
            "market": {
                "symbol": candle_in.symbol,
                "timeframe": candle_in.timeframe,
                "price": candle_in.close,
                "timestamp": candle_in.timestamp.isoformat(),
            },
            "status": {
                "system_status": "operational",
                "market_data_status": "connected (MT5 Direct Feed)",
                "telegram_status": "enabled" if settings.telegram_enabled else "disabled",
                "signal_engine_status": "running",
            },
        }
        if vals:
            payload["indicators"] = {
                "EMA9": vals.ema_fast,
                "EMA21": vals.ema_slow,
                "RSI": vals.rsi,
                "ADX": vals.adx,
                "DI+": vals.di_plus,
                "DI-": vals.di_minus,
                "SMA81": vals.sma_81,
                "ATR": vals.atr,
            }
        await broadcaster.publish("candle_update", payload)
    except Exception as exc:
        logger.error("SSE broadcast error: %s", exc)

    return {
        "ok": True,
        "symbol": candle_in.symbol,
        "timestamp": candle_in.timestamp,
        "close": candle_in.close,
        "signals_generated": len(signals_generated),
    }


@router.post(
    "/market/history",
    summary="Push historical candles from MT5",
    description="Backfills historical candle bars from MetaTrader 5 on initial EA attach.",
)
async def push_mt5_history(
    history_in: MT5HistoryIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    scheduler = _get_scheduler(request)
    normalized_list = [
        NormalizedCandle(
            timestamp=c.timestamp,
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
        )
        for c in history_in.candles
    ]

    signal_svc = scheduler._signal_service if scheduler is not None else getattr(request.app.state, "signal_service", None)
    if signal_svc is None:
        from app.services.signal_service import SignalService
        signal_svc = SignalService()
        await signal_svc.initialize(session)
        request.app.state.signal_service = signal_svc

    if normalized_list:
        await signal_svc.evaluate(normalized_list, session)

    return {
        "ok": True,
        "count": len(normalized_list),
        "message": f"Successfully ingested {len(normalized_list)} historical MT5 candles",
    }
