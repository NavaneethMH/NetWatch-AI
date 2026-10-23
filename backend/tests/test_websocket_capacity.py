"""
Phase 13.1 WebSocket Concurrency & Capacity Bound Tests:
1. Normal client connection admitted.
2. Configured maximum is enforced under concurrent admission.
3. Excess connection is rejected with close code 4003.
4. Disconnecting releases slot immediately.
5. Setup exceptions do not leak capacity.
6. Repeated cycles do not leak capacity.
7. 1.5s slow-client timeout remains isolated.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket
from backend.services.broadcaster import TelemetryBroadcaster


@pytest.mark.anyio
async def test_websocket_capacity_enforcement():
    """Verify that TelemetryBroadcaster strictly limits connections to max_clients (e.g. 5)."""
    broadcaster = TelemetryBroadcaster(max_clients=5)
    sockets = [AsyncMock(spec=WebSocket) for _ in range(5)]

    # Connect 5 clients
    for ws in sockets:
        accepted = await broadcaster.connect(ws)
        assert accepted is True
        ws.accept.assert_called_once()

    assert len(broadcaster._active_connections) == 5

    # 6th client attempt must be rejected with code 4003
    excess_ws = AsyncMock(spec=WebSocket)
    accepted = await broadcaster.connect(excess_ws)
    assert accepted is False
    excess_ws.close.assert_called_once_with(code=4003, reason="Maximum connections exceeded")
    assert len(broadcaster._active_connections) == 5

    # Disconnecting one client releases capacity
    broadcaster.disconnect(sockets[0])
    assert len(broadcaster._active_connections) == 4

    # Now a new client can connect
    new_ws = AsyncMock(spec=WebSocket)
    accepted = await broadcaster.connect(new_ws)
    assert accepted is True
    assert len(broadcaster._active_connections) == 5


@pytest.mark.anyio
async def test_websocket_concurrent_connection_attempts():
    """Verify concurrent connection attempts cannot breach max_clients limit."""
    MAX = 10
    broadcaster = TelemetryBroadcaster(max_clients=MAX)
    
    # Attempt 25 simultaneous connections
    candidates = [AsyncMock(spec=WebSocket) for _ in range(25)]

    results = await asyncio.gather(*(broadcaster.connect(ws) for ws in candidates))
    
    accepted_count = sum(1 for r in results if r is True)
    rejected_count = sum(1 for r in results if r is False)

    assert accepted_count == MAX
    assert rejected_count == 15
    assert len(broadcaster._active_connections) == MAX

    # Check that all rejected clients received close(code=4003)
    for ws in candidates:
        if ws not in broadcaster._active_connections:
            ws.close.assert_called_once_with(code=4003, reason="Maximum connections exceeded")


@pytest.mark.anyio
async def test_websocket_slow_client_eviction_preserved():
    """Verify that slow clients timing out during broadcast are safely evicted."""
    broadcaster = TelemetryBroadcaster(max_clients=5)
    
    # Healthy client
    healthy_ws = AsyncMock(spec=WebSocket)
    healthy_ws.send_text = AsyncMock()
    
    # Stalled client that sleeps longer than timeout (simulated hang)
    stalled_ws = AsyncMock(spec=WebSocket)
    async def slow_send(text):
        await asyncio.sleep(2.0)
    stalled_ws.send_text = slow_send

    await broadcaster.connect(healthy_ws)
    await broadcaster.connect(stalled_ws)
    assert len(broadcaster._active_connections) == 2

    # Broadcast
    await broadcaster.broadcast({"type": "telemetry", "test": 123})

    # Stalled client should be evicted, healthy remains
    assert healthy_ws in broadcaster._active_connections
    assert stalled_ws not in broadcaster._active_connections
    assert len(broadcaster._active_connections) == 1


@pytest.mark.anyio
async def test_websocket_repeated_cycles_no_leak():
    """Verify repeated connect/disconnect cycles cleanly restore available capacity without drift."""
    broadcaster = TelemetryBroadcaster(max_clients=3)
    ws = AsyncMock(spec=WebSocket)

    for _ in range(50):
        ok = await broadcaster.connect(ws)
        assert ok is True
        assert len(broadcaster._active_connections) == 1
        broadcaster.disconnect(ws)
        assert len(broadcaster._active_connections) == 0

    # Ensure capacity remains fully intact
    sockets = [AsyncMock(spec=WebSocket) for _ in range(3)]
    for s in sockets:
        assert (await broadcaster.connect(s)) is True
    assert len(broadcaster._active_connections) == 3


@pytest.mark.anyio
async def test_websocket_setup_exception_does_not_leak_capacity():
    """Verify that if websocket.accept() raises an exception during connect, capacity is not leaked."""
    broadcaster = TelemetryBroadcaster(max_clients=2)
    failing_ws = AsyncMock(spec=WebSocket)
    failing_ws.accept.side_effect = RuntimeError("Handshake aborted by client")

    with pytest.raises(RuntimeError):
        await broadcaster.connect(failing_ws)

    # Slot must not be occupied
    assert failing_ws not in broadcaster._active_connections
    assert len(broadcaster._active_connections) == 0

    # Normal connections still succeed up to full capacity
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    assert (await broadcaster.connect(ws1)) is True
    assert (await broadcaster.connect(ws2)) is True
    assert len(broadcaster._active_connections) == 2

