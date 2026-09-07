"""
Telegram Alert Service for XAUUSD Gold Signal System.

Dispatches formatted BUY/SELL alert messages to a configured Telegram
chat/channel when a valid signal is generated. Credentials are read
exclusively from environment variables and are never logged or exposed.

Retry policy: up to 3 attempts with exponential back-off (2 s, 4 s).
"""

import asyncio
import http.client
import json
import logging
import socket
from typing import Any, Dict, Optional, Tuple

from app.config import get_settings
from app.models.enums import SignalType
from app.models.signal import Signal

logger = logging.getLogger(__name__)


# ── IPv4-only HTTP helper ──────────────────────────────────────────────────────
# anyio's async TCP stack resolves addresses independently of socket.getaddrinfo
# patches, so we use a synchronous http.client approach (run in a thread) that
# explicitly requests AF_INET to avoid broken IPv6 routes on some networks.

def _ipv4_addrs(host: str, port: int) -> list:
    """Return AF_INET socket addresses for *host*:*port* only."""
    return [
        res[4]
        for res in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    ]


def _sync_telegram_request(
    token: str,
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
    base_url: str = "https://api.telegram.org",
) -> Dict[str, Any]:
    """
    Synchronous Telegram Bot API request.
    If using api.telegram.org, explicitly forces an IPv4 TCP socket to bypass
    broken IPv6 routes. If using a reverse proxy (e.g. Cloudflare Worker),
    connects directly to the proxy host over standard HTTPS/HTTP.
    """
    import urllib.parse
    import ssl as _ssl

    parsed = urllib.parse.urlparse(base_url.rstrip("/"))
    host = parsed.hostname or "api.telegram.org"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    base_path = parsed.path.rstrip("/")
    path = f"{base_path}/bot{token}/{endpoint}"

    method = "POST" if payload is not None else "GET"
    body: Optional[bytes] = None
    headers: Dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))

    if host == "api.telegram.org":
        # Force IPv4 socket for direct api.telegram.org to bypass IPv6 blackholes
        addrs = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
        if not addrs:
            raise ConnectionError(f"Could not resolve {host} to an IPv4 address")
        ipv4_addr = addrs[0][4]

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(timeout)
        raw_sock.connect(ipv4_addr)

        ctx = _ssl.create_default_context()
        ssl_sock = ctx.wrap_socket(raw_sock, server_hostname=host)

        conn = http.client.HTTPSConnection(host, 443, timeout=timeout)
        conn.sock = ssl_sock
    else:
        # Custom reverse proxy (e.g., Cloudflare Worker)
        if parsed.scheme == "http":
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, port, timeout=timeout)

    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    raw_text = response.read().decode("utf-8")
    conn.close()
    return json.loads(raw_text)



class TelegramService:
    """Sends formatted Telegram alerts for BUY/SELL signals."""

    _MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = (
            f"{self.settings.telegram_api_base_url.rstrip('/')}/bot{self.settings.telegram_bot_token}"
        )

    # ── Message Formatting ────────────────────────────────────────────────────

    def format_signal(self, signal: Signal) -> Optional[str]:
        """
        Return a formatted Telegram message for the given signal, or None
        if the signal type should not generate an alert (WAIT, or NO_ENTRY
        when NO_ENTRY_TELEGRAM_ALERTS is disabled).
        """
        sig_type = signal.signal_type.value if hasattr(signal.signal_type, "value") else str(signal.signal_type or "")
        if sig_type in (SignalType.WAIT.value, "WAIT"):
            return None

        if (
            sig_type in (SignalType.NO_ENTRY.value, "NO_ENTRY")
            and not self.settings.no_entry_telegram_alerts
        ):
            return None

        src = signal.signal_source.value if hasattr(signal.signal_source, "value") else str(signal.signal_source or "")

        if src == "SMA_81":
            return self._format_sma(signal)
        elif src == "EMA_RSI_ADX":
            return self._format_ema(signal)

        return None

    def _format_sma(self, signal: Signal) -> Optional[str]:
        if signal.signal_type == SignalType.BUY:
            return (
                "🟢 XAUUSD SMA BUY\n\n"
                "System: SMA 81\n"
                f"Timeframe: {signal.timeframe}\n\n"
                "Price crossed ABOVE SMA 81.\n\n"
                f"Price: {signal.price}\n"
                f"SMA 81: {signal.sma_81}\n\n"
                "Signal generated on candle close."
            )
        if signal.signal_type == SignalType.SELL:
            return (
                "🔴 XAUUSD SMA SELL\n\n"
                "System: SMA 81\n"
                f"Timeframe: {signal.timeframe}\n\n"
                "Price crossed BELOW SMA 81.\n\n"
                f"Price: {signal.price}\n"
                f"SMA 81: {signal.sma_81}\n\n"
                "Signal generated on candle close."
            )
        return None

    def _format_ema(self, signal: Signal) -> Optional[str]:
        if signal.signal_type == SignalType.BUY:
            return (
                "🟢 XAUUSD BUY SIGNAL\n\n"
                "System: EMA + RSI + ADX\n"
                f"Timeframe: {signal.timeframe}\n\n"
                f"Price: {signal.price}\n\n"
                f"EMA 9: {signal.ema_fast}\n"
                f"EMA 21: {signal.ema_slow}\n\n"
                f"RSI: {signal.rsi}\n"
                f"ADX: {signal.adx}\n"
                f"DI+: {signal.di_plus}\n"
                f"DI-: {signal.di_minus}\n\n"
                f"SMA 81: {signal.sma_81}\n"
                f"ATR 14: {signal.atr}\n\n"
                f"Trend: {signal.trend}\n\n"
                "Signal generated on candle close."
            )
        if signal.signal_type == SignalType.SELL:
            return (
                "🔴 XAUUSD SELL SIGNAL\n\n"
                "System: EMA + RSI + ADX\n"
                f"Timeframe: {signal.timeframe}\n\n"
                f"Price: {signal.price}\n\n"
                f"EMA 9: {signal.ema_fast}\n"
                f"EMA 21: {signal.ema_slow}\n\n"
                f"RSI: {signal.rsi}\n"
                f"ADX: {signal.adx}\n"
                f"DI+: {signal.di_plus}\n"
                f"DI-: {signal.di_minus}\n\n"
                f"SMA 81: {signal.sma_81}\n"
                f"ATR 14: {signal.atr}\n\n"
                f"Trend: {signal.trend}\n\n"
                "Signal generated on candle close."
            )
        return None

    # ── HTTP Dispatch ─────────────────────────────────────────────────────────

    async def _send_request(self, text: str) -> None:
        """
        POST a message to the Telegram Bot API via a thread-pool executor.
        Uses an IPv4-only http.client connection to avoid broken IPv6 TLS routes.
        Retries up to _MAX_ATTEMPTS times with exponential back-off.
        Raises the final exception if all attempts fail.
        """
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            logger.warning(
                "Telegram credentials not configured. Skipping message dispatch."
            )
            return

        payload = {"chat_id": self.settings.telegram_chat_id, "text": text}
        token = self.settings.telegram_bot_token

        base_url = self.settings.telegram_api_base_url
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                data = await asyncio.to_thread(
                    _sync_telegram_request,
                    token,
                    "sendMessage",
                    payload,
                    10.0,
                    base_url,
                )
                if not data.get("ok"):
                    raise RuntimeError(f"Telegram API error: {data.get('description')})")
                return
            except Exception as exc:
                if attempt == self._MAX_ATTEMPTS:
                    raise
                wait_secs = 2 ** attempt
                logger.warning(
                    "Telegram send failed (attempt %d/%d): %s. "
                    "Retrying in %ds...",
                    attempt,
                    self._MAX_ATTEMPTS,
                    exc,
                    wait_secs,
                )
                await asyncio.sleep(wait_secs)

    async def send_message(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Send a plain-text message to Telegram.
        Returns ``(True, None)`` on success or ``(False, error_string)`` on failure.
        """
        try:
            await self._send_request(text)
            return True, None
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = f"Telegram Error: {exc}"
            logger.error(error_msg)
            return False, error_msg

    # ── Connectivity Test ─────────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        """
        Call the Telegram ``getMe`` endpoint to verify that the bot token is
        valid and the API is reachable.
        Returns True on success.
        """
        if not self.settings.telegram_bot_token:
            logger.warning("Telegram bot token is not configured.")
            return False

        try:
            data = await asyncio.to_thread(
                _sync_telegram_request,
                self.settings.telegram_bot_token,
                "getMe",
                None,
                10.0,
                self.settings.telegram_api_base_url,
            )
            if data.get("ok"):
                logger.info(
                    "Telegram bot connected: @%s",
                    data["result"]["username"],
                )
                return True
            return False
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Telegram connectivity test failed: %s", exc)
            return False
