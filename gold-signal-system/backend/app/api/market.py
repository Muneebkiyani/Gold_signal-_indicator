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
