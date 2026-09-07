"""
Script to test Telegram Bot connection and send a test message.
Usage:
    python test_telegram_connection.py
"""
import asyncio
import sys
from app.config import get_settings
from app.services.telegram import TelegramService

async def main():
    settings = get_settings()
    print("=" * 60)
    print("XAUUSD Gold Signal System — Telegram Connection Test")
    print("=" * 60)
    print(f"Telegram Enabled: {settings.telegram_enabled}")
    print(f"Bot Token Configured: {'YES (masked)' if settings.telegram_bot_token else 'NO'}")
    print(f"Chat ID Configured: {settings.telegram_chat_id if settings.telegram_chat_id else 'NO'}")
    print(f"Telegram Base URL: {settings.telegram_api_base_url}")
    print("-" * 60)

    if not settings.telegram_bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in backend/.env")
        sys.exit(1)

    if not settings.telegram_chat_id:
        print("❌ Error: TELEGRAM_CHAT_ID is not set in backend/.env")
        sys.exit(1)

    service = TelegramService()

    print("1. Testing bot connectivity via getMe API...")
    connected = await service.test_connection()
    if not connected:
        print("❌ Bot connectivity test failed! Please check your TELEGRAM_BOT_TOKEN.")
        sys.exit(1)
    print("✅ Bot connected successfully!")

    print("\n2. Sending test alert message to Telegram chat...")
    test_message = (
        "🚀 XAUUSD Gold Signal System\n\n"
        "✅ Telegram Connection Verified!\n"
        "System is now ready to dispatch real-time M15 Gold trading signals.\n\n"
        "• Instrument: XAUUSD\n"
        "• Timeframe: M15\n"
        "• Alerts: BUY / SELL Active"
    )
    success, error = await service.send_message(test_message)
    if success:
        print("✅ Test message delivered to your Telegram chat successfully!")
        print("=" * 60)
        print("🎉 Telegram is fully connected and ready!")
    else:
        print(f"❌ Failed to deliver message: {error}")
        print("Hint: Make sure you opened your bot in Telegram and clicked /start first!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
