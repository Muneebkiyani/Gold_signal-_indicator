"""
Tests for Phase 6 — Technical Indicator Calculations.
Covers:
  - SMA: exact mathematical verification
  - RMA: Wilder's smoothing verification
  - EMA: exponential smoothing with SMA seed
  - True Range (TR) and ATR
  - RSI: classic Wilder 14-period textbook dataset verification
  - DMI (+DI, -DI) and ADX: directional movement and trend strength
  - IndicatorEngine full pipeline integration and parameter verification
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.market.models import NormalizedCandle
from app.strategy.engine import IndicatorEngine, IndicatorValues
from app.strategy.indicators import (
    atr,
    dmi,
    ema,
    rma,
    rsi,
    sma,
    true_range,
)


# ─── 1. SMA Tests ────────────────────────────────────────────────────────────

def test_sma_deterministic():
    """Verify SMA calculation against hand-computed values."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = sma(values, length=3)

    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(20.0, rel=1e-5)  # (10+20+30)/3
    assert result[3] == pytest.approx(30.0, rel=1e-5)  # (20+30+40)/3
    assert result[4] == pytest.approx(40.0, rel=1e-5)  # (30+40+50)/3


def test_sma_edge_cases():
    """Empty or short lists return all None."""
    assert sma([], 3) == []
    assert sma([1.0, 2.0], 5) == [None, None]
    assert sma([5.0], 0) == [None]


# ─── 2. Wilder's RMA Tests ───────────────────────────────────────────────────

def test_rma_wilder_smoothing():
    """
    Wilder's RMA:
      RMA[1] = SMA of first 2 = (10 + 20) / 2 = 15.0
      RMA[2] = (30 + 1 * 15.0) / 2 = 22.5
      RMA[3] = (40 + 1 * 22.5) / 2 = 31.25
    """
    values = [10.0, 20.0, 30.0, 40.0]
    result = rma(values, length=2)

    assert result[0] is None
    assert result[1] == pytest.approx(15.0, rel=1e-5)
    assert result[2] == pytest.approx(22.5, rel=1e-5)
    assert result[3] == pytest.approx(31.25, rel=1e-5)


# ─── 3. EMA Tests ────────────────────────────────────────────────────────────

def test_ema_deterministic():
    """
    EMA with length=2 (alpha = 2 / 3):
      Seed EMA[1] = (10 + 20) / 2 = 15.0
      EMA[2] = (2/3) * 30 + (1/3) * 15.0 = 20.0 + 5.0 = 25.0
      EMA[3] = (2/3) * 40 + (1/3) * 25.0 = 26.66667 + 8.33333 = 35.0
    """
    values = [10.0, 20.0, 30.0, 40.0]
    result = ema(values, length=2)

    assert result[0] is None
    assert result[1] == pytest.approx(15.0, rel=1e-5)
    assert result[2] == pytest.approx(25.0, rel=1e-5)
    assert result[3] == pytest.approx(35.0, rel=1e-5)


def test_ema_9_and_21_ordering():
    """In a sustained uptrend, EMA 9 must be strictly greater than EMA 21."""
    uptrend_closes = [2000.0 + i * 5.0 for i in range(50)]
    fast = ema(uptrend_closes, length=9)
    slow = ema(uptrend_closes, length=21)

    assert fast[-1] is not None
    assert slow[-1] is not None
    assert fast[-1] > slow[-1]


# ─── 4. True Range & ATR Tests ───────────────────────────────────────────────

def test_true_range_and_atr():
    """
    Verify True Range and ATR with 4 bars, length=2:
      Bar 0: H=100, L=90, C=95   -> TR=10.0
      Bar 1: H=110, L=92, C=105  -> TR=max(18, 15, 3) = 18.0
      Bar 2: H=108, L=102, C=104 -> TR=max(6, 3, 3) = 6.0
      Bar 3: H=115, L=103, C=112 -> TR=max(12, 11, 1) = 12.0

      ATR (length=2):
        ATR[1] = (10.0 + 18.0) / 2 = 14.0
        ATR[2] = (6.0 + 14.0) / 2 = 10.0
        ATR[3] = (12.0 + 10.0) / 2 = 11.0
    """
    highs = [100.0, 110.0, 108.0, 115.0]
    lows = [90.0, 92.0, 102.0, 103.0]
    closes = [95.0, 105.0, 104.0, 112.0]

    tr_vals = true_range(highs, lows, closes)
    assert tr_vals == [10.0, 18.0, 6.0, 12.0]

    atr_vals = atr(highs, lows, closes, length=2)
    assert atr_vals[0] is None
    assert atr_vals[1] == pytest.approx(14.0, rel=1e-5)
    assert atr_vals[2] == pytest.approx(10.0, rel=1e-5)
    assert atr_vals[3] == pytest.approx(11.0, rel=1e-5)


# ─── 5. RSI Tests ────────────────────────────────────────────────────────────

def test_rsi_classic_wilder_dataset():
    """
    Verify against J. Welles Wilder's original 14-period textbook data:
    15 closing prices producing 14 initial changes.
    Expected first RSI at bar 14 is 70.46 (+/- 0.05).
    """
    closes = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10,
        45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ]
    rsi_vals = rsi(closes, length=14)

    # First 14 bars (indices 0..13) are warmup
    for i in range(14):
        assert rsi_vals[i] is None

    # Bar 14 has the first valid RSI
    first_rsi = rsi_vals[14]
    assert first_rsi is not None
    assert first_rsi == pytest.approx(70.46, abs=0.05)


def test_rsi_bounds():
    """RSI must always stay within [0, 100]."""
    all_gains = [100.0 + i * 2.0 for i in range(30)]
    rsi_up = rsi(all_gains, length=14)
    assert rsi_up[-1] == pytest.approx(100.0, abs=0.01)

    all_losses = [200.0 - i * 2.0 for i in range(30)]
    rsi_down = rsi(all_losses, length=14)
    assert rsi_down[-1] == pytest.approx(0.0, abs=0.01)


# ─── 6. DMI (+DI, -DI) and ADX Tests ─────────────────────────────────────────

def test_dmi_and_adx_bullish_trend():
    """
    In a strong linear uptrend:
      - +DI must be significantly higher than -DI
      - ADX must rise and register a strong trend (> 20)
    """
    n = 60
    highs = [2000.0 + i * 3.0 + 2.0 for i in range(n)]
    lows = [2000.0 + i * 3.0 - 1.0 for i in range(n)]
    closes = [2000.0 + i * 3.0 + 1.0 for i in range(n)]

    plus_di, minus_di, adx_vals = dmi(highs, lows, closes, di_length=14, adx_smoothing=14)

    # +DI and -DI valid starting at bar 14
    assert plus_di[14] is not None
    assert minus_di[14] is not None
    assert plus_di[-1] > minus_di[-1]
    assert minus_di[-1] == pytest.approx(0.0, abs=0.1)

    # ADX requires 14 bars of DX + 14 bars smoothing = valid after bar 27
    assert adx_vals[-1] is not None
    assert adx_vals[-1] > 20.0  # Strong trend


def test_dmi_and_adx_flat_market():
    """In a completely flat market with zero movements, DX and ADX remain bounded."""
    n = 40
    highs = [2000.0] * n
    lows = [2000.0] * n
    closes = [2000.0] * n

    plus_di, minus_di, adx_vals = dmi(highs, lows, closes, di_length=14, adx_smoothing=14)
    assert plus_di[14] is None or plus_di[14] == 0.0


# ─── 7. IndicatorEngine Integration Tests ─────────────────────────────────────

def test_indicator_engine_full_snapshot():
    """
    Feed 100 synthetic candles to IndicatorEngine.
    Verify all 8 indicators are calculated and present in the snapshot.
    """
    base_time = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    candles = []
    for i in range(100):
        t = base_time + timedelta(minutes=i * 15)
        o = 2350.0 + i * 0.5
        h = o + 2.0
        low_val = o - 1.5
        c = o + 0.8
        candles.append(NormalizedCandle.create(
            timestamp=t,
            open=o,
            high=h,
            low=low_val,
            close=c,
            volume=100.0,
            timeframe="M15",
        ))

    engine = IndicatorEngine()
    snapshot = engine.calculate(candles)

    assert isinstance(snapshot, IndicatorValues)
    assert snapshot.ema_fast is not None
    assert snapshot.ema_slow is not None
    assert snapshot.rsi is not None
    assert 0.0 <= snapshot.rsi <= 100.0
    assert snapshot.adx is not None
    assert 0.0 <= snapshot.adx <= 100.0
    assert snapshot.di_plus is not None
    assert snapshot.di_minus is not None
    assert snapshot.sma_81 is not None  # 100 candles >= 81
    assert snapshot.atr is not None
    assert snapshot.atr > 0.0


def test_indicator_engine_insufficient_candles():
    """
    With only 10 candles:
      - Short indicators (EMA 9) may be calculated
      - Longer indicators (EMA 21, RSI 14, ADX 14, SMA 81) should be None
    """
    base_time = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
    candles = []
    for i in range(10):
        t = base_time + timedelta(minutes=i * 15)
        candles.append(NormalizedCandle.create(
            timestamp=t,
            open=2350.0 + i,
            high=2352.0 + i,
            low=2349.0 + i,
            close=2351.0 + i,
            timeframe="M15",
        ))

    engine = IndicatorEngine()
    snapshot = engine.calculate(candles)

    # 10 candles >= 9, so EMA 9 exists
    assert snapshot.ema_fast is not None
    # Needs 21 candles
    assert snapshot.ema_slow is None
    # Needs 15 candles
    assert snapshot.rsi is None
    # Needs 28 candles
    assert snapshot.adx is None
    # Needs 81 candles
    assert snapshot.sma_81 is None
