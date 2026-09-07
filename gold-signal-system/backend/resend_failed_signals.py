"""
Script to resend any failed / pending BUY and SELL signals to Telegram.
"""
import asyncio
import logging
from app.database import AsyncSessionLocal
from app.crud.signal import get_signals, update_telegram_status
from app.services.telegram import TelegramService
from app.models.enums import SignalType

logging.basicConfig(level=logging.INFO)

async def main():
    service = TelegramService()
    async with AsyncSessionLocal() as session:
        # Fetch all signals
        signals = await get_signals(session, limit=200)
        
        # Filter for unsent BUY / SELL signals only
        unsent = [
            s for s in signals 
            if not s.telegram_sent and s.signal_type in (SignalType.BUY, SignalType.SELL, "BUY", "SELL")
        ]
        # Order from oldest to newest
        unsent.sort(key=lambda s: s.candle_time)

        print("=" * 60)
        print(f"Found {len(unsent)} unsent BUY/SELL signal(s) to resend to Telegram:")
        print("=" * 60)

        sent_count = 0
        failed_count = 0

        for sig in unsent:
            msg = service.format_signal(sig)
            if not msg:
                print(f"⏩ Signal #{sig.id} has no formatted message, skipping.")
                continue

            sig_type = sig.signal_type.value if hasattr(sig.signal_type, "value") else str(sig.signal_type)
            print(f"• Sending Signal #{sig.id}: {sig_type} at {sig.price} ({sig.candle_time})...")
            
            success, err = await service.send_message(msg)
            await update_telegram_status(session, sig.id, sent=success, error=err)

            if success:
                print(f"  ✅ Signal #{sig.id} delivered successfully!")
                sent_count += 1
            else:
                print(f"  ❌ Signal #{sig.id} failed: {err}")
                failed_count += 1

            # Brief pause to respect Telegram rate limits
            await asyncio.sleep(0.5)

        print("=" * 60)
        print(f"Done! Sent: {sent_count}, Failed: {failed_count}")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
