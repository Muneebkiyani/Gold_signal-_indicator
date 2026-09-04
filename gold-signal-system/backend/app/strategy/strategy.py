"""
Exact Pine Script Strategy Logic for XAUUSD Gold Signal Alert System.

Authoritative Specification from TradingView Pine Script:
---------------------------------------------------------
1. EMA/RSI/ADX BUY:
   - Bullish Crossover: previous EMA9 <= previous EMA21 AND current EMA9 > current EMA21
   - RSI > 50 AND RSI < 70
   - ADX > 20
   - DI+ > DI-

2. EMA/RSI/ADX SELL:
   - Bearish Crossover: previous EMA9 >= previous EMA21 AND current EMA9 < current EMA21
   - RSI < 50 AND RSI > 30
   - ADX > 20
   - DI- > DI+

3. NO ENTRY (Transition into disqualified zone):
   - weakTrend: ADX < 20
   - rsiExtreme: RSI >= 70 OR RSI <= 30
   - noEntryZone: weakTrend OR rsiExtreme
   - noEntryStart: current noEntryZone AND NOT previous noEntryZone

4. SMA 81 Strategy (SEPARATE system — NEVER combined with EMA/RSI/ADX):
   - Bullish BUY: previous close <= previous SMA81 AND current close > current SMA81
   - Bearish SELL: previous close >= previous SMA81 AND current close < current SMA81

5. Trend Direction:
   - UP: ADX > 20 AND DI+ > DI-
   - DOWN: ADX > 20 AND DI- > DI+
   - otherwise: WEAK
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.market.models import NormalizedCandle
from app.models.enums import SignalSource, SignalType
from app.models.signal import Signal
from app.strategy.engine import IndicatorEngine

logger = logging.getLogger(__name__)


# ─── Trend Evaluation ─────────────────────────────────────────────────────────

def evaluate_trend(
    adx: Optional[float],
    di_plus: Optional[float],
    di_minus: Optional[float],
    adx_threshold: float = 20.0,
) -> str:
    """
    Evaluate trend direction strictly according to Pine Script spec:
      - UP: ADX > 20 AND DI+ > DI-
      - DOWN: ADX > 20 AND DI- > DI+
      - otherwise: WEAK
    """
    if adx is None or di_plus is None or di_minus is None:
        return "WEAK"

    if adx > adx_threshold and di_plus > di_minus:
        return "UP"
    elif adx > adx_threshold and di_minus > di_plus:
        return "DOWN"
    return "WEAK"


# ─── Strategy Output Model ────────────────────────────────────────────────────

class StrategySignal(BaseModel):
    """
    Structured output of a strategy evaluation on a completed candle.
    """
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(description="Instrument symbol, e.g. XAUUSD")
    timeframe: str = Field(description="Candle timeframe, e.g. M15")
    signal_type: SignalType = Field(description="Signal type: WAIT | BUY | SELL | NO_ENTRY")
    signal_source: SignalSource = Field(description="Strategy rule: EMA_RSI_ADX | SMA_81")
    price: float = Field(description="Close price of the evaluated candle")
    candle_time: datetime = Field(description="UTC timestamp of the evaluated candle")

    # Indicator snapshot
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    rsi: Optional[float] = None
    adx: Optional[float] = None
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None
    sma_81: Optional[float] = None
    atr: Optional[float] = None
    trend: str = Field(default="WEAK", description="Trend direction: UP | DOWN | WEAK")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Signal generation timestamp (UTC)",
    )

    def to_db_signal(self) -> Signal:
        """Convert to database Signal SQLModel table instance."""
        return Signal(
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal_type=self.signal_type.value,
            signal_source=self.signal_source.value,
            candle_time=self.candle_time,
            price=self.price,
            ema_fast=self.ema_fast,
            ema_slow=self.ema_slow,
            rsi=self.rsi,
            adx=self.adx,
            di_plus=self.di_plus,
            di_minus=self.di_minus,
            sma_81=self.sma_81,
            atr=self.atr,
            trend=self.trend,
        )


# ─── EMA / RSI / ADX Strategy ────────────────────────────────────────────────

def evaluate_ema_rsi_adx(
    candles: Sequence[NormalizedCandle],
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    engine: Optional[IndicatorEngine] = None,
) -> StrategySignal:
    """
    Evaluate the EMA/RSI/ADX strategy on the latest completed candle.

    Conditions:
      BUY:
        previous EMA9 <= previous EMA21 AND current EMA9 > current EMA21
        AND current RSI > 50 AND current RSI < 70
        AND current ADX > 20
        AND current DI+ > current DI-

      SELL:
        previous EMA9 >= previous EMA21 AND current EMA9 < current EMA21
        AND current RSI < 50 AND current RSI > 30
        AND current ADX > 20
        AND current DI- > current DI+

      NO_ENTRY:
        weakTrend: ADX < 20
        rsiExtreme: RSI >= 70 OR RSI <= 30
        noEntryZone: weakTrend OR rsiExtreme
        noEntryStart: current noEntryZone AND NOT previous noEntryZone

      WAIT:
        Otherwise
    """
    eng = engine or IndicatorEngine()

    if len(candles) < 2:
        # Not enough history to detect crossover
        latest_c = candles[-1] if candles else None
        return StrategySignal(
            symbol=symbol,
            timeframe=timeframe,
            signal_type=SignalType.WAIT,
            signal_source=SignalSource.EMA_RSI_ADX,
            price=latest_c.close if latest_c else 0.0,
            candle_time=latest_c.timestamp if latest_c else datetime.now(timezone.utc),
            trend="WEAK",
        )

    series = eng.calculate_series(candles)
    curr_ind = series[-1]
    prev_ind = series[-2]
    curr_candle = candles[-1]

    trend = evaluate_trend(curr_ind.adx, curr_ind.di_plus, curr_ind.di_minus)

    # Base snapshot
    base_kwargs = {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal_source": SignalSource.EMA_RSI_ADX,
        "price": curr_candle.close,
        "candle_time": curr_candle.timestamp,
        "ema_fast": curr_ind.ema_fast,
        "ema_slow": curr_ind.ema_slow,
        "rsi": curr_ind.rsi,
        "adx": curr_ind.adx,
        "di_plus": curr_ind.di_plus,
        "di_minus": curr_ind.di_minus,
        "sma_81": curr_ind.sma_81,
        "atr": curr_ind.atr,
        "trend": trend,
    }

    # Verify all required indicators are available
    required_curr = (
        curr_ind.ema_fast, curr_ind.ema_slow, curr_ind.rsi,
        curr_ind.adx, curr_ind.di_plus, curr_ind.di_minus,
    )
    required_prev = (prev_ind.ema_fast, prev_ind.ema_slow, prev_ind.rsi, prev_ind.adx)

    if any(v is None for v in required_curr) or any(v is None for v in required_prev):
        return StrategySignal(signal_type=SignalType.WAIT, **base_kwargs)

    # 1. Crossovers
    ema_cross_up = (prev_ind.ema_fast <= prev_ind.ema_slow) and (curr_ind.ema_fast > curr_ind.ema_slow)
    ema_cross_down = (prev_ind.ema_fast >= prev_ind.ema_slow) and (curr_ind.ema_fast < curr_ind.ema_slow)

    # 2. BUY check
    if (
        ema_cross_up
        and 50.0 < curr_ind.rsi < 70.0
        and curr_ind.adx > 20.0
        and curr_ind.di_plus > curr_ind.di_minus
    ):
        return StrategySignal(signal_type=SignalType.BUY, **base_kwargs)

    # 3. SELL check
    if (
        ema_cross_down
        and 30.0 < curr_ind.rsi < 50.0
        and curr_ind.adx > 20.0
        and curr_ind.di_minus > curr_ind.di_plus
    ):
        return StrategySignal(signal_type=SignalType.SELL, **base_kwargs)

    # 4. NO_ENTRY check (entry into disqualified zone)
    curr_weak_trend = curr_ind.adx < 20.0
    curr_rsi_extreme = curr_ind.rsi >= 70.0 or curr_ind.rsi <= 30.0
    curr_no_entry_zone = curr_weak_trend or curr_rsi_extreme

    prev_weak_trend = prev_ind.adx < 20.0
    prev_rsi_extreme = prev_ind.rsi >= 70.0 or prev_ind.rsi <= 30.0
    prev_no_entry_zone = prev_weak_trend or prev_rsi_extreme

    no_entry_start = curr_no_entry_zone and not prev_no_entry_zone

    if no_entry_start:
        return StrategySignal(signal_type=SignalType.NO_ENTRY, **base_kwargs)

    # 5. Default WAIT
    return StrategySignal(signal_type=SignalType.WAIT, **base_kwargs)


# ─── SMA 81 Strategy ─────────────────────────────────────────────────────────

def evaluate_sma_81(
    candles: Sequence[NormalizedCandle],
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    engine: Optional[IndicatorEngine] = None,
) -> StrategySignal:
    """
    Evaluate the SMA 81 price crossover strategy on the latest completed candle.

    CRITICAL RULE:
      NEVER combine SMA 81 with EMA/RSI/ADX. This is an independent signal source.

    Conditions:
      BUY:
        previous close <= previous SMA81 AND current close > current SMA81

      SELL:
        previous close >= previous SMA81 AND current close < current SMA81

      WAIT:
        Otherwise
    """
    eng = engine or IndicatorEngine()

    if len(candles) < 2:
        latest_c = candles[-1] if candles else None
        return StrategySignal(
            symbol=symbol,
            timeframe=timeframe,
            signal_type=SignalType.WAIT,
            signal_source=SignalSource.SMA_81,
            price=latest_c.close if latest_c else 0.0,
            candle_time=latest_c.timestamp if latest_c else datetime.now(timezone.utc),
            trend="WEAK",
        )

    series = eng.calculate_series(candles)
    curr_ind = series[-1]
    prev_ind = series[-2]
    curr_candle = candles[-1]
    prev_candle = candles[-2]

    trend = evaluate_trend(curr_ind.adx, curr_ind.di_plus, curr_ind.di_minus)

    base_kwargs = {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal_source": SignalSource.SMA_81,
        "price": curr_candle.close,
        "candle_time": curr_candle.timestamp,
        "ema_fast": curr_ind.ema_fast,
        "ema_slow": curr_ind.ema_slow,
        "rsi": curr_ind.rsi,
        "adx": curr_ind.adx,
        "di_plus": curr_ind.di_plus,
        "di_minus": curr_ind.di_minus,
        "sma_81": curr_ind.sma_81,
        "atr": curr_ind.atr,
        "trend": trend,
    }

    # Verify SMA 81 is available for both current and previous candle
    if curr_ind.sma_81 is None or prev_ind.sma_81 is None:
        return StrategySignal(signal_type=SignalType.WAIT, **base_kwargs)

    # Bullish price crossover above SMA 81
    price_cross_up = (prev_candle.close <= prev_ind.sma_81) and (curr_candle.close > curr_ind.sma_81)
    if price_cross_up:
        return StrategySignal(signal_type=SignalType.BUY, **base_kwargs)

    # Bearish price crossover below SMA 81
    price_cross_down = (prev_candle.close >= prev_ind.sma_81) and (curr_candle.close < curr_ind.sma_81)
    if price_cross_down:
        return StrategySignal(signal_type=SignalType.SELL, **base_kwargs)

    return StrategySignal(signal_type=SignalType.WAIT, **base_kwargs)


# ─── Evaluate All Strategies ─────────────────────────────────────────────────

def evaluate_strategies(
    candles: Sequence[NormalizedCandle],
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    engine: Optional[IndicatorEngine] = None,
) -> list[StrategySignal]:
    """
    Evaluate both strategies independently on the completed candle.
    Returns two signals: one for EMA_RSI_ADX and one for SMA_81.
    """
    sig_ema = evaluate_ema_rsi_adx(candles, symbol=symbol, timeframe=timeframe, engine=engine)
    sig_sma = evaluate_sma_81(candles, symbol=symbol, timeframe=timeframe, engine=engine)
    return [sig_ema, sig_sma]
