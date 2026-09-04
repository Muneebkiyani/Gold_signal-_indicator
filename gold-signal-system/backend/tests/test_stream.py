"""
Tests for Phase 13 — Real-Time Streaming (SSE) Layer.

Covers:
  - EventBroadcaster pub/sub mechanics and heartbeat
  - GET /api/stream endpoint response headers and media type
  - Initial snapshot delivery on client connection
  - Real-time event broadcasting and queue isolation
"""

from __future__ import annotations

import asyncio
import json
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.database import get_db
from app.main import app
from app.services.broadcaster import EventBroadcaster


@pytest.fixture
async def stream_client():
    """Provides an isolated database session and client for SSE testing."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def _override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_broadcaster_pub_sub():
    """Verify EventBroadcaster delivers events to subscribers."""
    broadcaster = EventBroadcaster()
    received = []

    async def _subscriber():
        gen = broadcaster.subscribe(heartbeat_interval=1.0)
        async for item in gen:
            received.append(item)
            if len(received) >= 2:
                break

    sub_task = asyncio.create_task(_subscriber())
    await asyncio.sleep(0.05)

    # Broadcast 2 events
    await broadcaster.broadcast("test_event_1", {"msg": "hello"})
    await broadcaster.broadcast("test_event_2", {"msg": "world"})

    await asyncio.wait_for(sub_task, timeout=2.0)
    assert len(received) == 2
    assert "test_event_1" in received[0]
    assert "hello" in received[0]
    assert "test_event_2" in received[1]
    assert "world" in received[1]


@pytest.mark.asyncio
async def test_broadcaster_initial_snapshot():
    """Verify subscriber receives initial snapshot immediately upon connecting."""
    broadcaster = EventBroadcaster()
    snapshot = {"snapshot": {"price": 2500.0, "signal": "BUY"}}
    received = []

    async def _subscriber():
        gen = broadcaster.subscribe(initial_data=snapshot, heartbeat_interval=1.0)
        async for item in gen:
            received.append(item)
            break

    await asyncio.wait_for(_subscriber(), timeout=2.0)
    assert len(received) == 1
    assert "snapshot" in received[0]
    assert "2500.0" in received[0]
    assert "BUY" in received[0]


@pytest.mark.asyncio
async def test_api_stream_endpoint(stream_client):
    """Verify GET /api/stream connects and yields text/event-stream."""
    client = stream_client

    # Connect with a streaming response
    async with client.stream("GET", "/api/stream?max_events=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Read the first chunk (which is the initial snapshot)
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line.replace("data: ", "")
                data = json.loads(data_str)
                assert data["type"] == "snapshot"
                assert "payload" in data
                assert "status" in data["payload"]
                assert "current_signal" in data["payload"]
                break
        await response.aclose()
