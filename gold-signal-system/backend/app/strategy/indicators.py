"""
Technical Indicator Calculations matching TradingView / Pine Script v5.

Implements exact formulas for:
  - SMA: ta.sma(source, length)
  - RMA: ta.rma(source, length) — Wilder's Moving Average
  - EMA: ta.ema(source, length) — with SMA initialization
  - TR & ATR: ta.tr and ta.atr(length) via Wilder's RMA
  - RSI: ta.rsi(source, length) via Wilder's RMA of gains/losses
  - DMI & ADX: [plusDI, minusDI, adx] = ta.dmi(diLength, adxSmoothing)
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple


# ─── 1. Simple Moving Average (SMA) ──────────────────────────────────────────

def sma(values: Sequence[float], length: int) -> list[Optional[float]]:
    """
    Calculate Simple Moving Average (SMA) matching TradingView ta.sma.

    Returns None for indices < length - 1.
    """
    n = len(values)
    result: list[Optional[float]] = [None] * n
    if n < length or length <= 0:
        return result

    current_sum = sum(values[:length])
    result[length - 1] = current_sum / length

    for i in range(length, n):
        current_sum += values[i] - values[i - length]
        result[i] = current_sum / length

    return result


# ─── 2. Wilder's Moving Average (RMA) ────────────────────────────────────────

def rma(values: Sequence[float], length: int) -> list[Optional[float]]:
    """
    Calculate Wilder's Moving Average (RMA) matching TradingView ta.rma.

    In Pine Script:
      alpha = 1 / length
      rma[length - 1] = sma(values[:length])
      rma[i] = alpha * values[i] + (1 - alpha) * rma[i - 1]
             = (values[i] + (length - 1) * rma[i - 1]) / length

    Returns None for indices < length - 1.
    """
    n = len(values)
    result: list[Optional[float]] = [None] * n
    if n < length or length <= 0:
        return result

    # First valid value is the SMA of the first `length` items
    first_sum = sum(values[:length])
    result[length - 1] = first_sum / length

    alpha = 1.0 / length
    one_minus_alpha = 1.0 - alpha

    for i in range(length, n):
        prev = result[i - 1]
        assert prev is not None
        result[i] = alpha * values[i] + one_minus_alpha * prev

    return result


# ─── 3. Exponential Moving Average (EMA) ─────────────────────────────────────

def ema(values: Sequence[float], length: int) -> list[Optional[float]]:
    """
    Calculate Exponential Moving Average (EMA) matching TradingView ta.ema.

    In Pine Script:
      alpha = 2 / (length + 1)
      ema[length - 1] = sma(values[:length])
      ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]

    Returns None for indices < length - 1.
    """
    n = len(values)
    result: list[Optional[float]] = [None] * n
    if n < length or length <= 0:
        return result

    # First valid value is the SMA of the first `length` items (TradingView standard)
    first_sum = sum(values[:length])
    result[length - 1] = first_sum / length

    alpha = 2.0 / (length + 1.0)
    one_minus_alpha = 1.0 - alpha

    for i in range(length, n):
        prev = result[i - 1]
        assert prev is not None
        result[i] = alpha * values[i] + one_minus_alpha * prev

    return result


# ─── 4. True Range (TR) and Average True Range (ATR) ─────────────────────────

def true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float]:
    """
    Calculate True Range matching TradingView ta.tr.

    TR[0] = high[0] - low[0]
    TR[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    """
    n = len(highs)
    if n == 0:
        return []

    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr.append(max(hl, hc, lc))
    return tr


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    length: int = 14,
) -> list[Optional[float]]:
    """
    Calculate Average True Range (ATR) matching TradingView ta.atr.

    In Pine Script: ta.atr(length) is ta.rma(ta.tr, length).
    Returns None for indices < length - 1.
    """
    tr = true_range(highs, lows, closes)
    return rma(tr, length)


# ─── 5. Relative Strength Index (RSI) ────────────────────────────────────────

def rsi(closes: Sequence[float], length: int = 14) -> list[Optional[float]]:
    """
    Calculate Relative Strength Index (RSI) matching TradingView ta.rsi.

    In Pine Script:
      up = ta.rma(max(change, 0), length)
      down = ta.rma(max(-change, 0), length)
      rsi = down == 0 ? 100 : up == 0 ? 0 : 100 - (100 / (1 + up / down))

    Returns None for indices < length.
    """
    n = len(closes)
    result: list[Optional[float]] = [None] * n
    if n <= length or length <= 0:
        return result

    # Calculate price changes starting from bar 1
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    # Apply RMA with period `length` over the changes
    rma_gains = rma(gains, length)
    rma_losses = rma(losses, length)

    # Align back to closes indexing (changes start at index 1 of closes)
    for i in range(len(rma_gains)):
        close_idx = i + 1
        avg_gain = rma_gains[i]
        avg_loss = rma_losses[i]

        if avg_gain is None or avg_loss is None:
            result[close_idx] = None
        elif avg_loss == 0.0:
            result[close_idx] = 100.0 if avg_gain > 0.0 else 50.0
        elif avg_gain == 0.0:
            result[close_idx] = 0.0
        else:
            rs = avg_gain / avg_loss
            result[close_idx] = 100.0 - (100.0 / (1.0 + rs))

    return result


# ─── 6. Directional Movement Index (DMI) and ADX ─────────────────────────────

def dmi(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    di_length: int = 14,
    adx_smoothing: int = 14,
) -> Tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    """
    Calculate Directional Movement Index (+DI, -DI) and ADX matching TradingView ta.dmi.

    Pine Script specification:
      up = ta.change(high)
      down = -ta.change(low)
      plusDM = (up > down and up > 0) ? up : 0
      minusDM = (down > up and down > 0) ? down : 0
      trur = ta.rma(ta.tr, diLength)
      plus = 100 * ta.rma(plusDM, diLength) / trur
      minus = 100 * ta.rma(minusDM, diLength) / trur
      sum = plus + minus
      dx = 100 * abs(plus - minus) / (sum == 0 ? 1 : sum)
      adx = ta.rma(dx, adxSmoothing)

    Returns:
      (plus_di, minus_di, adx)
    """
    n = len(highs)
    plus_di: list[Optional[float]] = [None] * n
    minus_di: list[Optional[float]] = [None] * n
    adx_values: list[Optional[float]] = [None] * n

    if n <= di_length or di_length <= 0 or adx_smoothing <= 0:
        return plus_di, minus_di, adx_values

    # Step 1: Directional Movement & True Range from bar 1
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr_list: list[float] = []

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        p_dm = up_move if (up_move > down_move and up_move > 0.0) else 0.0
        m_dm = down_move if (down_move > up_move and down_move > 0.0) else 0.0

        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr_val = max(hl, hc, lc)

        plus_dm.append(p_dm)
        minus_dm.append(m_dm)
        tr_list.append(tr_val)

    # Step 2: Smooth with RMA
    rma_p_dm = rma(plus_dm, di_length)
    rma_m_dm = rma(minus_dm, di_length)
    rma_tr = rma(tr_list, di_length)

    # Step 3: Compute +DI, -DI, and DX series
    dx_series: list[Optional[float]] = []

    for k in range(len(rma_tr)):
        close_idx = k + 1
        s_p = rma_p_dm[k]
        s_m = rma_m_dm[k]
        s_tr = rma_tr[k]

        if s_p is None or s_m is None or s_tr is None or s_tr == 0.0:
            plus_di[close_idx] = None
            minus_di[close_idx] = None
            dx_series.append(None)
        else:
            p_val = 100.0 * (s_p / s_tr)
            m_val = 100.0 * (s_m / s_tr)
            plus_di[close_idx] = p_val
            minus_di[close_idx] = m_val

            di_sum = p_val + m_val
            if di_sum == 0.0:
                dx_series.append(0.0)
            else:
                dx_val = 100.0 * (abs(p_val - m_val) / di_sum)
                dx_series.append(dx_val)

    # Step 4: Smooth DX with RMA to get ADX
    # Filter out initial None values to align RMA correctly
    valid_dx = [x for x in dx_series if x is not None]
    if len(valid_dx) >= adx_smoothing:
        smoothed_dx = rma(valid_dx, adx_smoothing)
        # Map smoothed_dx back to closes indexing
        offset = (di_length - 1)  # number of Nones before first valid DX in dx_series
        for m, adx_val in enumerate(smoothed_dx):
            target_idx = offset + m + 1
            if target_idx < n:
                adx_values[target_idx] = adx_val

    return plus_di, minus_di, adx_values
