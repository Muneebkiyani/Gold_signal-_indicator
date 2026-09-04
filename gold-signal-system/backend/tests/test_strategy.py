"""
Comprehensive tests for Phase 7 — Exact Pine Script Strategy Logic.
Tests every condition independently:
  - EMA/RSI/ADX BUY (all conditions met vs. each failing condition)
  - EMA/RSI/ADX SELL (all conditions met vs. each failing condition)
  - Crossover detection (exact previous vs current rules)
  - NO ENTRY detection (weak trend, RSI extreme, transition only)
  - SMA 81 price crossovers (Bullish BUY, Bearish SELL, no cross)
  - Trend evaluation (UP, DOWN, WEAK)
  - Independence of SMA 81 and EMA/RSI/ADX systems
  - Conversion to DB Signal model
"""

from datetime import datetime, timezone
import pytest

from app.models.enums import SignalSource, SignalType
from app.strategy.engine import IndicatorEngine, IndicatorValues
from app.strategy.strategy import (
    StrategySignal,
    evaluate_ema_rsi_adx,
    evaluate_sma_81,
    evaluate_strategies,
    evaluate_trend,
)
from app.market.models import NormalizedCandle


# ─── Mock IndicatorEngine for Deterministic Condition Testing ─────────────────

class DeterministicIndicatorEngine:
    """Mock engine that returns predefined IndicatorValues for testing exact strategy branches."""

    def __init__(self, series: list[IndicatorValues]) -> None:
        self.series = series

    def calculate_series(self, candles) -> list[IndicatorValues]:
        return self.series

    def calculate(self, candles) -> IndicatorValues:
        return self.series[-1]


def make_dummy_candles(n: int = 2) -> list[NormalizedCandle]:
    base = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    return [
        NormalizedCandle.create(
            timestamp=base,
            open=2350.0,
            high=2355.0,
            low=2345.0,
            close=2352.0,
        ),
        NormalizedCandle.create(
            timestamp=datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc),
            open=2352.0,
            high=2360.0,
            low=2350.0,
            close=2358.0,
        ),
    ]


# ─── 1. Trend Direction Tests ─────────────────────────────────────────────────

def test_trend_up():
    assert evaluate_trend(adx=25.0, di_plus=30.0, di_minus=15.0) == "UP"


def test_trend_down():
    assert evaluate_trend(adx=25.0, di_plus=15.0, di_minus=30.0) == "DOWN"


def test_trend_weak_due_to_adx():
    # ADX <= 20 must always evaluate to WEAK
    assert evaluate_trend(adx=19.9, di_plus=35.0, di_minus=10.0) == "WEAK"
    assert evaluate_trend(adx=20.0, di_plus=35.0, di_minus=10.0) == "WEAK"


def test_trend_weak_equal_di():
    assert evaluate_trend(adx=25.0, di_plus=20.0, di_minus=20.0) == "WEAK"


def test_trend_none_values():
    assert evaluate_trend(None, 25.0, 15.0) == "WEAK"
    assert evaluate_trend(25.0, None, 15.0) == "WEAK"
    assert evaluate_trend(25.0, 25.0, None) == "WEAK"


# ─── 2. EMA/RSI/ADX BUY Tests ─────────────────────────────────────────────────

def test_ema_rsi_adx_buy_valid():
    """All 5 BUY conditions met simultaneously -> BUY."""
    candles = make_dummy_candles()
    series = [
        # Previous bar: EMA9 <= EMA21, normal RSI/ADX
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=22.0, di_plus=25.0, di_minus=15.0),
        # Current bar: Crossover (EMA9 > EMA21), RSI in (50, 70), ADX > 20, DI+ > DI-
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=24.0, di_plus=28.0, di_minus=12.0),
    ]
    engine = DeterministicIndicatorEngine(series)
    sig = evaluate_ema_rsi_adx(candles, engine=engine)

    assert sig.signal_type == SignalType.BUY
    assert sig.signal_source == SignalSource.EMA_RSI_ADX
    assert sig.trend == "UP"


def test_ema_rsi_adx_buy_fails_no_crossover():
    """Fast was already above slow previously -> No crossover -> WAIT."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2348.0, ema_slow=2345.0, rsi=55.0, adx=25.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2350.0, ema_slow=2346.0, rsi=60.0, adx=25.0, di_plus=28.0, di_minus=12.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


def test_ema_rsi_adx_buy_fails_rsi_too_low():
    """RSI <= 50 -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=45.0, adx=25.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=49.9, adx=25.0, di_plus=28.0, di_minus=12.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


def test_ema_rsi_adx_buy_fails_rsi_too_high():
    """RSI >= 70 -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=65.0, adx=25.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=72.0, adx=25.0, di_plus=28.0, di_minus=12.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type != SignalType.BUY


def test_ema_rsi_adx_buy_fails_adx_too_low():
    """ADX <= 20 -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=18.0, di_plus=25.0, di_minus=15.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=19.5, di_plus=28.0, di_minus=12.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type != SignalType.BUY


def test_ema_rsi_adx_buy_fails_di_negative():
    """DI+ <= DI- -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=25.0, di_plus=15.0, di_minus=25.0),
        IndicatorValues(ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=25.0, di_plus=18.0, di_minus=22.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


# ─── 3. EMA/RSI/ADX SELL Tests ────────────────────────────────────────────────

def test_ema_rsi_adx_sell_valid():
    """All 5 SELL conditions met simultaneously -> SELL."""
    candles = make_dummy_candles()
    series = [
        # Previous bar: EMA9 >= EMA21
        IndicatorValues(ema_fast=2350.0, ema_slow=2345.0, rsi=45.0, adx=24.0, di_plus=15.0, di_minus=25.0),
        # Current bar: Crossover (EMA9 < EMA21), RSI in (30, 50), ADX > 20, DI- > DI+
        IndicatorValues(ema_fast=2342.0, ema_slow=2345.0, rsi=40.0, adx=26.0, di_plus=12.0, di_minus=28.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))

    assert sig.signal_type == SignalType.SELL
    assert sig.signal_source == SignalSource.EMA_RSI_ADX
    assert sig.trend == "DOWN"


def test_ema_rsi_adx_sell_fails_no_crossover():
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2345.0, rsi=45.0, adx=25.0, di_plus=10.0, di_minus=25.0),
        IndicatorValues(ema_fast=2338.0, ema_slow=2345.0, rsi=40.0, adx=25.0, di_plus=10.0, di_minus=25.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


def test_ema_rsi_adx_sell_fails_rsi_too_low():
    """RSI <= 30 -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2345.0, rsi=35.0, adx=25.0, di_plus=10.0, di_minus=25.0),
        IndicatorValues(ema_fast=2342.0, ema_slow=2345.0, rsi=28.0, adx=25.0, di_plus=10.0, di_minus=25.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type != SignalType.SELL


def test_ema_rsi_adx_sell_fails_rsi_too_high():
    """RSI >= 50 -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2345.0, rsi=55.0, adx=25.0, di_plus=10.0, di_minus=25.0),
        IndicatorValues(ema_fast=2342.0, ema_slow=2345.0, rsi=52.0, adx=25.0, di_plus=10.0, di_minus=25.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


def test_ema_rsi_adx_sell_fails_adx_too_low():
    """ADX <= 20 -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2345.0, rsi=40.0, adx=18.0, di_plus=10.0, di_minus=25.0),
        IndicatorValues(ema_fast=2342.0, ema_slow=2345.0, rsi=40.0, adx=19.5, di_plus=10.0, di_minus=25.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type != SignalType.SELL


def test_ema_rsi_adx_sell_fails_di_positive():
    """DI- <= DI+ -> rejected."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2345.0, rsi=40.0, adx=25.0, di_plus=22.0, di_minus=18.0),
        IndicatorValues(ema_fast=2342.0, ema_slow=2345.0, rsi=40.0, adx=25.0, di_plus=22.0, di_minus=18.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


# ─── 4. NO ENTRY Tests ────────────────────────────────────────────────────────

def test_no_entry_transition_on_weak_trend():
    """Previous bar had ADX >= 20, current bar drops into ADX < 20 -> NO_ENTRY."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=55.0, adx=22.0, di_plus=20.0, di_minus=15.0),
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=55.0, adx=18.5, di_plus=20.0, di_minus=15.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.NO_ENTRY


def test_no_entry_transition_on_rsi_extreme_overbought():
    """RSI jumps from 65 to 72 -> NO_ENTRY."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=65.0, adx=25.0, di_plus=20.0, di_minus=15.0),
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=72.0, adx=25.0, di_plus=20.0, di_minus=15.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.NO_ENTRY


def test_no_entry_transition_on_rsi_extreme_oversold():
    """RSI drops from 35 to 28 -> NO_ENTRY."""
    candles = make_dummy_candles()
    series = [
        IndicatorValues(ema_fast=2340.0, ema_slow=2348.0, rsi=35.0, adx=25.0, di_plus=15.0, di_minus=20.0),
        IndicatorValues(ema_fast=2340.0, ema_slow=2348.0, rsi=28.0, adx=25.0, di_plus=15.0, di_minus=20.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.NO_ENTRY


def test_no_entry_continuous_zone_emits_wait():
    """
    If the previous bar was ALREADY in no-entry zone,
    the current bar does NOT re-emit NO_ENTRY. It stays WAIT.
    """
    candles = make_dummy_candles()
    series = [
        # Previous was already weak trend (ADX=18 < 20)
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=55.0, adx=18.0, di_plus=20.0, di_minus=15.0),
        # Current is still weak trend (ADX=16 < 20)
        IndicatorValues(ema_fast=2350.0, ema_slow=2348.0, rsi=55.0, adx=16.0, di_plus=20.0, di_minus=15.0),
    ]
    sig = evaluate_ema_rsi_adx(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


# ─── 5. SMA 81 Tests ─────────────────────────────────────────────────────────

def test_sma_81_buy_crossover():
    """previous close <= previous SMA81 AND current close > current SMA81 -> BUY."""
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)

    candles = [
        NormalizedCandle.create(timestamp=t0, open=2335, high=2342, low=2334, close=2339.0),
        NormalizedCandle.create(timestamp=t1, open=2339, high=2346, low=2338, close=2345.0),
    ]
    series = [
        IndicatorValues(sma_81=2340.0),  # prev close (2339) <= prev SMA (2340)
        IndicatorValues(sma_81=2341.0),  # curr close (2345) > curr SMA (2341)
    ]
    sig = evaluate_sma_81(candles, engine=DeterministicIndicatorEngine(series))

    assert sig.signal_type == SignalType.BUY
    assert sig.signal_source == SignalSource.SMA_81
    assert sig.price == 2345.0


def test_sma_81_sell_crossover():
    """previous close >= previous SMA81 AND current close < current SMA81 -> SELL."""
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)

    candles = [
        NormalizedCandle.create(timestamp=t0, open=2345, high=2348, low=2340, close=2342.0),
        NormalizedCandle.create(timestamp=t1, open=2342, high=2343, low=2334, close=2336.0),
    ]
    series = [
        IndicatorValues(sma_81=2340.0),  # prev close (2342) >= prev SMA (2340)
        IndicatorValues(sma_81=2339.0),  # curr close (2336) < curr SMA (2339)
    ]
    sig = evaluate_sma_81(candles, engine=DeterministicIndicatorEngine(series))

    assert sig.signal_type == SignalType.SELL
    assert sig.signal_source == SignalSource.SMA_81
    assert sig.price == 2336.0


def test_sma_81_no_crossover_emits_wait():
    """Price stays above SMA81 on both bars -> WAIT."""
    t0 = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc)

    candles = [
        NormalizedCandle.create(timestamp=t0, open=2345, high=2348, low=2340, close=2344.0),
        NormalizedCandle.create(timestamp=t1, open=2344, high=2349, low=2343, close=2347.0),
    ]
    series = [
        IndicatorValues(sma_81=2340.0),
        IndicatorValues(sma_81=2341.0),
    ]
    sig = evaluate_sma_81(candles, engine=DeterministicIndicatorEngine(series))
    assert sig.signal_type == SignalType.WAIT


# ─── 6. Independence of Strategies & Conversion to DB Signal ──────────────────

def test_evaluate_strategies_separate_outputs():
    """
    CRITICAL RULE:
    Do not combine SMA 81 with EMA/RSI/ADX.
    evaluate_strategies must return 2 independent StrategySignals.
    """
    candles = make_dummy_candles()
    series = [
        IndicatorValues(
            ema_fast=2340.0, ema_slow=2345.0, rsi=55.0, adx=25.0,
            di_plus=25.0, di_minus=15.0, sma_81=2360.0,
        ),
        IndicatorValues(
            ema_fast=2348.0, ema_slow=2346.0, rsi=60.0, adx=25.0,
            di_plus=28.0, di_minus=12.0, sma_81=2360.0,
        ),
    ]
    signals = evaluate_strategies(candles, engine=DeterministicIndicatorEngine(series))

    assert len(signals) == 2
    ema_sig = signals[0]
    sma_sig = signals[1]

    assert ema_sig.signal_source == SignalSource.EMA_RSI_ADX
    assert ema_sig.signal_type == SignalType.BUY

    assert sma_sig.signal_source == SignalSource.SMA_81
    assert sma_sig.signal_type == SignalType.WAIT

    # Convert to DB model
    db_sig = ema_sig.to_db_signal()
    assert db_sig.signal_type == "BUY"
    assert db_sig.signal_source == "EMA_RSI_ADX"
    assert db_sig.price == candles[-1].close
    assert db_sig.telegram_sent is False
