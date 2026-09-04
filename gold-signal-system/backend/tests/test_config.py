"""
Tests for app/config.py — Settings loading, validation, and security.

These tests exercise:
  - Default values for all fields
  - Environment variable overrides
  - Field validators (log_level, timeframe, symbol)
  - Model validators (EMA ordering, RSI band ordering)
  - Numeric range constraints
  - Secret masking in safe_dict() and __repr__()
  - Cache behaviour of get_settings()
"""

import os
import pytest

from pydantic import ValidationError


# ── Helpers ───────────────────────────────────────────────────────────────────

def fresh_settings(**env_overrides):
    """
    Import Settings fresh (bypassing the lru_cache) with optional env overrides.
    Uses monkeypatching via os.environ so pydantic-settings picks them up.
    """
    # Apply overrides to os.environ temporarily
    original = {}
    for k, v in env_overrides.items():
        original[k] = os.environ.get(k)
        os.environ[k] = str(v)

    try:
        # Clear the cache so get_settings() creates a new instance
        from app.config import get_settings, Settings
        get_settings.cache_clear()
        # Create directly (not via cache) for isolation
        return Settings(_env_file=None)  # skip .env file in tests
    finally:
        # Restore original env
        for k, orig_v in original.items():
            if orig_v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig_v
        from app.config import get_settings
        get_settings.cache_clear()


# ═════════════════════════════════════════════════════════════════════════════
# 1. Default values
# ═════════════════════════════════════════════════════════════════════════════

class TestDefaults:
    def test_symbol_default(self):
        s = fresh_settings()
        assert s.symbol == "XAUUSD"

    def test_timeframe_default(self):
        s = fresh_settings()
        assert s.timeframe == "M15"

    def test_ema_defaults(self):
        s = fresh_settings()
        assert s.ema_fast == 9
        assert s.ema_slow == 21

    def test_rsi_defaults(self):
        s = fresh_settings()
        assert s.rsi_length == 14
        assert s.rsi_mid == 50.0
        assert s.rsi_overbought == 70.0
        assert s.rsi_oversold == 30.0

    def test_adx_defaults(self):
        s = fresh_settings()
        assert s.adx_length == 14
        assert s.adx_smoothing == 14
        assert s.adx_min == 20.0

    def test_sma_default(self):
        s = fresh_settings()
        assert s.sma_length == 81

    def test_atr_default(self):
        s = fresh_settings()
        assert s.atr_length == 14

    def test_signal_on_close_default(self):
        s = fresh_settings()
        assert s.signal_on_close is True

    def test_no_entry_telegram_default(self):
        s = fresh_settings()
        assert s.no_entry_telegram_alerts is False

    def test_telegram_disabled_by_default(self):
        s = fresh_settings()
        assert s.telegram_enabled is False

    def test_secrets_empty_by_default(self):
        s = fresh_settings()
        assert s.data_provider_api_key == ""
        assert s.telegram_bot_token == ""
        assert s.telegram_chat_id == ""

    def test_database_url_default(self):
        s = fresh_settings()
        assert "signals.db" in s.database_url

    def test_debug_false_by_default(self):
        s = fresh_settings()
        assert s.debug is False

    def test_log_level_default(self):
        s = fresh_settings()
        assert s.log_level == "INFO"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Environment variable overrides
# ═════════════════════════════════════════════════════════════════════════════

class TestEnvOverrides:
    def test_symbol_override(self):
        s = fresh_settings(SYMBOL="EURUSD")
        assert s.symbol == "EURUSD"

    def test_symbol_lowercased_in_env_is_uppercased(self):
        s = fresh_settings(SYMBOL="xauusd")
        assert s.symbol == "XAUUSD"

    def test_timeframe_override(self):
        s = fresh_settings(TIMEFRAME="H4")
        assert s.timeframe == "H4"

    def test_timeframe_case_insensitive(self):
        s = fresh_settings(TIMEFRAME="h1")
        assert s.timeframe == "H1"

    def test_ema_override(self):
        s = fresh_settings(EMA_FAST=5, EMA_SLOW=50)
        assert s.ema_fast == 5
        assert s.ema_slow == 50

    def test_rsi_override(self):
        s = fresh_settings(RSI_LENGTH=21, RSI_MID=55, RSI_OVERBOUGHT=75, RSI_OVERSOLD=25)
        assert s.rsi_length == 21
        assert s.rsi_mid == 55.0
        assert s.rsi_overbought == 75.0
        assert s.rsi_oversold == 25.0

    def test_adx_override(self):
        s = fresh_settings(ADX_LENGTH=20, ADX_SMOOTHING=20, ADX_MIN=25)
        assert s.adx_length == 20
        assert s.adx_smoothing == 20
        assert s.adx_min == 25.0

    def test_sma_override(self):
        s = fresh_settings(SMA_LENGTH=200)
        assert s.sma_length == 200

    def test_atr_override(self):
        s = fresh_settings(ATR_LENGTH=20)
        assert s.atr_length == 20

    def test_signal_on_close_false(self):
        s = fresh_settings(SIGNAL_ON_CLOSE="false")
        assert s.signal_on_close is False

    def test_no_entry_alerts_true(self):
        s = fresh_settings(NO_ENTRY_TELEGRAM_ALERTS="true")
        assert s.no_entry_telegram_alerts is True

    def test_telegram_enabled_override(self):
        s = fresh_settings(TELEGRAM_ENABLED="true")
        assert s.telegram_enabled is True

    def test_database_url_override(self):
        s = fresh_settings(DATABASE_URL="sqlite+aiosqlite:///./custom.db")
        assert s.database_url == "sqlite+aiosqlite:///./custom.db"

    def test_log_level_override(self):
        s = fresh_settings(LOG_LEVEL="DEBUG")
        assert s.log_level == "DEBUG"

    def test_debug_override(self):
        s = fresh_settings(DEBUG="true")
        assert s.debug is True

    def test_api_key_override(self):
        s = fresh_settings(DATA_PROVIDER_API_KEY="secret-key-123")
        assert s.data_provider_api_key == "secret-key-123"

    def test_base_url_override(self):
        s = fresh_settings(DATA_PROVIDER_BASE_URL="https://api.example.com")
        assert s.data_provider_base_url == "https://api.example.com"


# ═════════════════════════════════════════════════════════════════════════════
# 3. Field validators — log_level
# ═════════════════════════════════════════════════════════════════════════════

class TestLogLevelValidator:
    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_valid_log_levels(self, level):
        s = fresh_settings(LOG_LEVEL=level)
        assert s.log_level == level

    def test_log_level_lowercased_accepted(self):
        s = fresh_settings(LOG_LEVEL="debug")
        assert s.log_level == "DEBUG"

    def test_invalid_log_level_raises(self):
        with pytest.raises(ValidationError, match="log_level"):
            fresh_settings(LOG_LEVEL="VERBOSE")


# ═════════════════════════════════════════════════════════════════════════════
# 4. Field validators — timeframe
# ═════════════════════════════════════════════════════════════════════════════

class TestTimeframeValidator:
    @pytest.mark.parametrize("tf", ["M1", "M5", "M15", "M30", "H1", "H4", "D1"])
    def test_valid_timeframes(self, tf):
        s = fresh_settings(TIMEFRAME=tf)
        assert s.timeframe == tf

    def test_invalid_timeframe_raises(self):
        with pytest.raises(ValidationError, match="timeframe"):
            fresh_settings(TIMEFRAME="W1")


# ═════════════════════════════════════════════════════════════════════════════
# 5. Field validators — symbol
# ═════════════════════════════════════════════════════════════════════════════

class TestSymbolValidator:
    def test_symbol_uppercased(self):
        s = fresh_settings(SYMBOL="xauusd")
        assert s.symbol == "XAUUSD"

    def test_symbol_trimmed(self):
        s = fresh_settings(SYMBOL="  XAUUSD  ")
        assert s.symbol == "XAUUSD"

    def test_empty_symbol_raises(self):
        with pytest.raises(ValidationError, match="symbol"):
            fresh_settings(SYMBOL="")


# ═════════════════════════════════════════════════════════════════════════════
# 6. Model validators — EMA ordering
# ═════════════════════════════════════════════════════════════════════════════

class TestEMAOrdering:
    def test_fast_equals_slow_raises(self):
        with pytest.raises(ValidationError, match="EMA_FAST"):
            fresh_settings(EMA_FAST=21, EMA_SLOW=21)

    def test_fast_greater_than_slow_raises(self):
        with pytest.raises(ValidationError, match="EMA_FAST"):
            fresh_settings(EMA_FAST=50, EMA_SLOW=21)

    def test_valid_ema_ordering_passes(self):
        s = fresh_settings(EMA_FAST=5, EMA_SLOW=20)
        assert s.ema_fast < s.ema_slow


# ═════════════════════════════════════════════════════════════════════════════
# 7. Model validators — RSI band ordering
# ═════════════════════════════════════════════════════════════════════════════

class TestRSIBandOrdering:
    def test_oversold_equals_overbought_raises(self):
        with pytest.raises(ValidationError, match="RSI_OVERSOLD"):
            fresh_settings(RSI_OVERSOLD=70, RSI_OVERBOUGHT=70)

    def test_oversold_greater_raises(self):
        with pytest.raises(ValidationError, match="RSI_OVERSOLD"):
            fresh_settings(RSI_OVERSOLD=80, RSI_OVERBOUGHT=70)

    def test_valid_rsi_ordering_passes(self):
        s = fresh_settings(RSI_OVERSOLD=25, RSI_OVERBOUGHT=75)
        assert s.rsi_oversold < s.rsi_overbought


# ═════════════════════════════════════════════════════════════════════════════
# 8. Numeric range constraints
# ═════════════════════════════════════════════════════════════════════════════

class TestNumericRanges:
    def test_ema_fast_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(EMA_FAST=0, EMA_SLOW=21)

    def test_rsi_overbought_above_100_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(RSI_OVERBOUGHT=101)

    def test_rsi_oversold_below_0_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(RSI_OVERSOLD=-1)

    def test_adx_min_below_0_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(ADX_MIN=-5)

    def test_adx_min_above_100_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(ADX_MIN=101)

    def test_port_below_range_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(PORT=0)

    def test_port_above_range_raises(self):
        with pytest.raises(ValidationError):
            fresh_settings(PORT=99999)

    def test_sma_length_minimum(self):
        s = fresh_settings(SMA_LENGTH=1)
        assert s.sma_length == 1

    def test_atr_length_minimum(self):
        s = fresh_settings(ATR_LENGTH=1)
        assert s.atr_length == 1


# ═════════════════════════════════════════════════════════════════════════════
# 9. Security — secrets are masked in safe_dict() and __repr__()
# ═════════════════════════════════════════════════════════════════════════════

class TestSecretMasking:
    def test_api_key_masked_when_set(self):
        s = fresh_settings(DATA_PROVIDER_API_KEY="super-secret-key")
        safe = s.safe_dict()
        assert safe["data_provider_api_key"] == "***"
        assert "super-secret-key" not in str(safe)

    def test_api_key_shown_as_not_set_when_empty(self):
        s = fresh_settings(DATA_PROVIDER_API_KEY="")
        safe = s.safe_dict()
        assert safe["data_provider_api_key"] == "(not set)"

    def test_telegram_token_masked_when_set(self):
        s = fresh_settings(TELEGRAM_BOT_TOKEN="bot123:ABC")
        safe = s.safe_dict()
        assert safe["telegram_bot_token"] == "***"
        assert "bot123" not in str(safe)

    def test_telegram_chat_id_masked_when_set(self):
        s = fresh_settings(TELEGRAM_CHAT_ID="-100123456789")
        safe = s.safe_dict()
        assert safe["telegram_chat_id"] == "***"
        assert "-100123456789" not in str(safe)

    def test_repr_does_not_contain_api_key(self):
        s = fresh_settings(DATA_PROVIDER_API_KEY="my-secret")
        assert "my-secret" not in repr(s)

    def test_repr_does_not_contain_telegram_token(self):
        s = fresh_settings(TELEGRAM_BOT_TOKEN="secret-token")
        assert "secret-token" not in repr(s)

    def test_non_secret_visible_in_safe_dict(self):
        s = fresh_settings(SYMBOL="XAUUSD")
        safe = s.safe_dict()
        assert safe["symbol"] == "XAUUSD"


# ═════════════════════════════════════════════════════════════════════════════
# 10. Cache behaviour
# ═════════════════════════════════════════════════════════════════════════════

class TestCacheBehaviour:
    def test_get_settings_returns_same_instance(self):
        from app.config import get_settings
        get_settings.cache_clear()
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_cache_clear_returns_new_instance(self):
        from app.config import get_settings
        get_settings.cache_clear()
        a = get_settings()
        get_settings.cache_clear()
        b = get_settings()
        # Different objects (cache was cleared), but equal values
        assert a is not b
        assert a.symbol == b.symbol
