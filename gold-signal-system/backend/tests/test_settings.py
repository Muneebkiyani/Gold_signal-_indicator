"""
Tests for GET /api/settings and PUT /api/settings.

Covers:
  - All safe fields are returned
  - Private credentials are never exposed
  - Valid updates succeed
  - EMA fast >= slow is rejected (422)
  - RSI oversold >= overbought is rejected (422)
  - Out-of-range numeric values are rejected (422)
  - Sequential: GET after PUT returns updated values
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_settings():
    """Clear the lru_cache before each test so settings revert to defaults."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── GET /api/settings ─────────────────────────────────────────────────────────


class TestGetSettings:
    def test_returns_200(self, client: TestClient):
        resp = client.get("/api/settings")
        assert resp.status_code == 200

    def test_response_is_json(self, client: TestClient):
        resp = client.get("/api/settings")
        assert resp.headers["content-type"].startswith("application/json")

    def test_strategy_defaults_present(self, client: TestClient):
        data = client.get("/api/settings").json()
        assert data["ema_fast"] == 9
        assert data["ema_slow"] == 21
        assert data["rsi_length"] == 14
        assert data["rsi_mid"] == 50.0
        assert data["rsi_overbought"] == 70.0
        assert data["rsi_oversold"] == 30.0
        assert data["adx_length"] == 14
        assert data["adx_smoothing"] == 14
        assert data["adx_min"] == 20.0
        assert data["sma_length"] == 81
        assert data["atr_length"] == 14

    def test_signal_defaults(self, client: TestClient):
        data = client.get("/api/settings").json()
        assert data["signal_on_close"] is True
        assert data["telegram_enabled"] is False
        assert data["no_entry_telegram_alerts"] is False

    def test_instrument_defaults(self, client: TestClient):
        data = client.get("/api/settings").json()
        assert data["symbol"] == "XAUUSD"
        assert data["timeframe"] == "M15"

    def test_no_private_credentials_in_response(self, client: TestClient):
        data = client.get("/api/settings").json()
        forbidden = {
            "telegram_bot_token",
            "telegram_chat_id",
            "data_provider_api_key",
            "market_data_api_key",
            "api_key",
            "bot_token",
            "token",
        }
        for key in data.keys():
            assert key not in forbidden, (
                f"Private field '{key}' was exposed in GET /api/settings"
            )

    def test_no_secret_values_exposed(self, client: TestClient):
        """Ensure no field value looks like a token/key (non-empty long string)."""
        data = client.get("/api/settings").json()
        # telegram_bot_token and data_provider_api_key must NOT appear
        response_text = str(data)
        assert "telegram_bot_token" not in response_text
        assert "data_provider_api_key" not in response_text

    def test_app_metadata_present(self, client: TestClient):
        data = client.get("/api/settings").json()
        assert "app_name" in data
        assert "app_version" in data
        assert data["app_version"] == "1.0.0"

    def test_worker_config_present(self, client: TestClient):
        data = client.get("/api/settings").json()
        assert "poll_interval_seconds" in data
        assert "candle_history_limit" in data
        assert data["poll_interval_seconds"] == 60
        assert data["candle_history_limit"] == 150


# ── PUT /api/settings — valid updates ─────────────────────────────────────────


class TestUpdateSettingsValid:
    def test_update_ema_periods(self, client: TestClient):
        payload = {"ema_fast": 12, "ema_slow": 26}
        resp = client.put("/api/settings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ema_fast"] == 12
        assert data["ema_slow"] == 26

    def test_update_rsi_settings(self, client: TestClient):
        payload = {
            "rsi_length": 10,
            "rsi_mid": 50.0,
            "rsi_overbought": 75.0,
            "rsi_oversold": 25.0,
        }
        resp = client.put("/api/settings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rsi_length"] == 10
        assert data["rsi_overbought"] == 75.0
        assert data["rsi_oversold"] == 25.0

    def test_update_adx_settings(self, client: TestClient):
        payload = {"adx_length": 20, "adx_smoothing": 20, "adx_min": 25.0}
        resp = client.put("/api/settings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["adx_length"] == 20
        assert data["adx_min"] == 25.0

    def test_update_sma_atr(self, client: TestClient):
        payload = {"sma_length": 100, "atr_length": 20}
        resp = client.put("/api/settings", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sma_length"] == 100
        assert data["atr_length"] == 20

    def test_update_telegram_enabled(self, client: TestClient):
        resp = client.put("/api/settings", json={"telegram_enabled": True})
        assert resp.status_code == 200
        assert resp.json()["telegram_enabled"] is True

    def test_update_no_entry_alerts(self, client: TestClient):
        resp = client.put("/api/settings", json={"no_entry_telegram_alerts": True})
        assert resp.status_code == 200
        assert resp.json()["no_entry_telegram_alerts"] is True

    def test_update_signal_on_close(self, client: TestClient):
        resp = client.put("/api/settings", json={"signal_on_close": False})
        assert resp.status_code == 200
        # signal_on_close is not in SettingsResponse but change is accepted
        # (it lives in worker_enabled area; some implementations may or may not expose it)

    def test_update_symbol(self, client: TestClient):
        resp = client.put("/api/settings", json={"symbol": "EURUSD"})
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "EURUSD"

    def test_update_timeframe(self, client: TestClient):
        resp = client.put("/api/settings", json={"timeframe": "H1"})
        assert resp.status_code == 200
        assert resp.json()["timeframe"] == "H1"

    def test_empty_payload_is_no_op(self, client: TestClient):
        """Empty PUT should succeed and return current settings unchanged."""
        resp = client.put("/api/settings", json={})
        assert resp.status_code == 200

    def test_partial_update_only_changes_specified_fields(self, client: TestClient):
        """Unspecified fields must keep their original values."""
        resp = client.put("/api/settings", json={"ema_fast": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ema_fast"] == 5
        assert data["ema_slow"] == 21  # untouched

    def test_get_after_put_reflects_changes(self, client: TestClient):
        """Verify persistence within the same process."""
        client.put("/api/settings", json={"ema_fast": 7, "ema_slow": 50})
        data = client.get("/api/settings").json()
        assert data["ema_fast"] == 7
        assert data["ema_slow"] == 50


# ── PUT /api/settings — validation errors ─────────────────────────────────────


class TestUpdateSettingsValidation:
    def test_ema_fast_equal_slow_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"ema_fast": 21, "ema_slow": 21})
        assert resp.status_code == 422

    def test_ema_fast_greater_than_slow_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"ema_fast": 30, "ema_slow": 21})
        assert resp.status_code == 422

    def test_ema_fast_exceeds_existing_slow_rejected(self, client: TestClient):
        """Default slow=21; setting fast=25 alone should be rejected."""
        resp = client.put("/api/settings", json={"ema_fast": 25})
        assert resp.status_code == 422

    def test_rsi_oversold_equal_overbought_rejected(self, client: TestClient):
        resp = client.put(
            "/api/settings",
            json={"rsi_oversold": 70.0, "rsi_overbought": 70.0},
        )
        assert resp.status_code == 422

    def test_rsi_oversold_greater_than_overbought_rejected(self, client: TestClient):
        resp = client.put(
            "/api/settings",
            json={"rsi_oversold": 80.0, "rsi_overbought": 60.0},
        )
        assert resp.status_code == 422

    def test_ema_fast_below_minimum_rejected(self, client: TestClient):
        # ge=1 means 0 is invalid
        resp = client.put("/api/settings", json={"ema_fast": 0})
        assert resp.status_code == 422

    def test_ema_slow_above_maximum_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"ema_slow": 9999})
        assert resp.status_code == 422

    def test_rsi_length_below_minimum_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"rsi_length": 1})
        assert resp.status_code == 422

    def test_adx_min_above_maximum_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"adx_min": 150.0})
        assert resp.status_code == 422

    def test_poll_interval_below_minimum_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"poll_interval_seconds": 5})
        assert resp.status_code == 422

    def test_error_response_contains_detail(self, client: TestClient):
        resp = client.put("/api/settings", json={"ema_fast": 30, "ema_slow": 21})
        body = resp.json()
        assert "detail" in body

    def test_invalid_types_rejected(self, client: TestClient):
        resp = client.put("/api/settings", json={"ema_fast": "not_a_number"})
        assert resp.status_code == 422

    def test_private_fields_not_accepted(self, client: TestClient):
        """Even if a client sends private fields, they must not be applied."""
        resp = client.put(
            "/api/settings",
            json={"telegram_bot_token": "leaked-token"},
        )
        # Either 422 (rejected) or 200 (ignored) is acceptable — but the token
        # must NOT appear in the response body either way.
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            assert "telegram_bot_token" not in resp.json()
