"""
Indicator Engine — calculates complete technical indicator snapshots from candle series.

Matches configured strategy parameters:
  - EMA_FAST = 9
  - EMA_SLOW = 21
  - RSI_LENGTH = 14
  - ADX_LENGTH = 14
  - ADX_SMOOTHING = 14
  - SMA_LENGTH = 81
  - ATR_LENGTH = 14
"""

from __future__ import annotations

from typing import Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.market.models import NormalizedCandle
from app.strategy.indicators import (
    atr as calc_atr,
    dmi as calc_dmi,
    ema as calc_ema,
    rsi as calc_rsi,
    sma as calc_sma,
)


class IndicatorValues(BaseModel):
    """
    Structured snapshot of calculated technical indicators for a single candle.
    All values are Optional[float] to gracefully handle warmup periods.
    """
    model_config = ConfigDict(frozen=True)

    ema_fast: Optional[float] = Field(default=None, description="Fast Exponential Moving Average (default: 9)")
    ema_slow: Optional[float] = Field(default=None, description="Slow Exponential Moving Average (default: 21)")
    rsi: Optional[float] = Field(default=None, description="Relative Strength Index (default: 14)")
    adx: Optional[float] = Field(default=None, description="Average Directional Index (default: 14)")
    di_plus: Optional[float] = Field(default=None, description="Positive Directional Indicator +DI (default: 14)")
    di_minus: Optional[float] = Field(default=None, description="Negative Directional Indicator -DI (default: 14)")
    sma_81: Optional[float] = Field(default=None, description="81-period Simple Moving Average")
    atr: Optional[float] = Field(default=None, description="Average True Range (default: 14)")

    def to_dict(self) -> dict[str, Optional[float]]:
        return {
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "rsi": self.rsi,
            "adx": self.adx,
            "di_plus": self.di_plus,
            "di_minus": self.di_minus,
            "sma_81": self.sma_81,
            "atr": self.atr,
        }


class IndicatorEngine:
    """
    Engine that calculates TradingView-compatible technical indicators
    over a sequence of NormalizedCandles.
    """

    def __init__(
        self,
        ema_fast: Optional[int] = None,
        ema_slow: Optional[int] = None,
        rsi_length: Optional[int] = None,
        adx_length: Optional[int] = None,
        adx_smoothing: Optional[int] = None,
        sma_length: Optional[int] = None,
        atr_length: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.ema_fast = ema_fast if ema_fast is not None else settings.ema_fast
        self.ema_slow = ema_slow if ema_slow is not None else settings.ema_slow
        self.rsi_length = rsi_length if rsi_length is not None else settings.rsi_length
        self.adx_length = adx_length if adx_length is not None else settings.adx_length
        self.adx_smoothing = adx_smoothing if adx_smoothing is not None else settings.adx_smoothing
        self.sma_length = sma_length if sma_length is not None else settings.sma_length
        self.atr_length = atr_length if atr_length is not None else settings.atr_length

    def calculate_series(self, candles: Sequence[NormalizedCandle]) -> list[IndicatorValues]:
        """
        Calculate indicator values across all candles in chronological order.
        Returns a list of IndicatorValues matching the length of input candles.
        """
        n = len(candles)
        if n == 0:
            return []

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        # 1. EMAs
        ema_fast_series = calc_ema(closes, self.ema_fast)
        ema_slow_series = calc_ema(closes, self.ema_slow)

        # 2. RSI
        rsi_series = calc_rsi(closes, self.rsi_length)

        # 3. DMI & ADX
        plus_di_series, minus_di_series, adx_series = calc_dmi(
            highs=highs,
            lows=lows,
            closes=closes,
            di_length=self.adx_length,
            adx_smoothing=self.adx_smoothing,
        )

        # 4. SMA 81
        sma_81_series = calc_sma(closes, self.sma_length)

        # 5. ATR
        atr_series = calc_atr(highs, lows, closes, self.atr_length)

        # Assemble snapshots
        series: list[IndicatorValues] = []
        for i in range(n):
            series.append(
                IndicatorValues(
                    ema_fast=round(ema_fast_series[i], 4) if ema_fast_series[i] is not None else None,
                    ema_slow=round(ema_slow_series[i], 4) if ema_slow_series[i] is not None else None,
                    rsi=round(rsi_series[i], 4) if rsi_series[i] is not None else None,
                    adx=round(adx_series[i], 4) if adx_series[i] is not None else None,
                    di_plus=round(plus_di_series[i], 4) if plus_di_series[i] is not None else None,
                    di_minus=round(minus_di_series[i], 4) if minus_di_series[i] is not None else None,
                    sma_81=round(sma_81_series[i], 4) if sma_81_series[i] is not None else None,
                    atr=round(atr_series[i], 4) if atr_series[i] is not None else None,
                )
            )

        return series

    def calculate(self, candles: Sequence[NormalizedCandle]) -> IndicatorValues:
        """
        Calculate indicator values for the latest (most recent) candle.
        """
        series = self.calculate_series(candles)
        if not series:
            return IndicatorValues()
        return series[-1]
