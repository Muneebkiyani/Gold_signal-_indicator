"""
Event Broadcaster — Manages real-time Server-Sent Events (SSE) connections.
Provides asynchronous event dispatching to connected dashboard clients.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import AsyncGenerator, Dict, Optional, Set

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """
    Central event bus connecting the signal scheduler and market pipeline
    to SSE streaming endpoints.
    """

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()  # type: ignore[type-arg]
        self._lock = asyncio.Lock()

    async def broadcast(self, event_type: str, data: dict) -> None:
        """
        Dispatch an event payload to all active subscriber queues.
        Silently drops messages for overloaded clients to avoid blocking the pipeline.
        """
        message = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": data,
        }

        async with self._lock:
            active_count = len(self._subscribers)
            if active_count == 0:
                return

            for queue in list(self._subscribers):
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning("Subscriber queue full — dropping event %s", event_type)
                except Exception as exc:
                    logger.debug("Failed to enqueue event: %s", exc)

    async def subscribe(
        self,
        initial_data: Optional[Dict[str, dict]] = None,
        heartbeat_interval: float = 15.0,
        max_events: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Register a client queue and yield formatted SSE chunks.
        Sends keep-alive comments periodically if no events are emitted.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)  # type: ignore[type-arg]
        emitted = 0

        async with self._lock:
            self._subscribers.add(queue)
            logger.info("SSE client connected (total: %d)", len(self._subscribers))

        try:
            # 1. Send initial snapshot if provided
            if initial_data:
                for ev_type, ev_payload in initial_data.items():
                    init_msg = {
                        "type": ev_type,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": ev_payload,
                    }
                    yield f"data: {json.dumps(init_msg)}\n\n"
                    emitted += 1
                    if max_events is not None and emitted >= max_events:
                        return

            # 2. Event loop with heartbeat
            while True:
                if max_events is not None and emitted >= max_events:
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    yield f"data: {json.dumps(msg)}\n\n"
                    emitted += 1
                except asyncio.TimeoutError:
                    # Keep-alive comment per SSE spec
                    yield ": ping\n\n"

        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            async with self._lock:
                self._subscribers.discard(queue)
                logger.info("SSE client disconnected (remaining: %d)", len(self._subscribers))


_broadcaster_instance: Optional[EventBroadcaster] = None


def get_broadcaster() -> EventBroadcaster:
    """Return the singleton EventBroadcaster instance."""
    global _broadcaster_instance
    if _broadcaster_instance is None:
        _broadcaster_instance = EventBroadcaster()
    return _broadcaster_instance
