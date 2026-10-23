"""WebSocket Connection Manager and Telemetry Broadcaster (Phase 5)
Provides an in-memory pub-sub dispatcher that sends the latest sampled telemetry
from the existing sampling engine to all active client connections without re-sampling.
Ensures slow or stalled clients are isolated with strict per-client timeouts so they
cannot block or delay telemetry delivery to other connected clients.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any, Optional
import asyncio
import logging
import json
from backend.core.config import settings

logger = logging.getLogger("netwatch.broadcaster")

class TelemetryBroadcaster:
    """Manages active WebSocket connections and broadcasts telemetry payloads.
    Caches the latest real snapshot and isolates slow clients via asyncio.gather and send timeouts.
    """

    def __init__(self, max_clients: Optional[int] = None):
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._latest_payload: Optional[Dict[str, Any]] = None
        self.max_clients = max_clients if max_clients is not None else settings.WS_MAX_CLIENTS

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_latest_payload(self, payload: Dict[str, Any]):
        """Caches the latest real persisted sample payload."""
        self._latest_payload = payload

    def get_latest_payload(self) -> Optional[Dict[str, Any]]:
        return self._latest_payload

    async def connect(self, websocket: WebSocket) -> bool:
        """Atomically checks capacity and registers websocket client.
        If at capacity, closes with policy violation code 4003 (or 4408) and returns False.
        """
        async with self._lock:
            if len(self._active_connections) >= self.max_clients:
                logger.warning(
                    f"WebSocket connection rejected: reached max client limit ({self.max_clients})."
                )
                # 4003 is standard WebSocket Policy Violation / Maximum Connections Exceeded
                await websocket.close(code=4003, reason="Maximum connections exceeded")
                return False

            await websocket.accept()
            self._active_connections.add(websocket)
            logger.info(f"WebSocket client connected. Active clients: {len(self._active_connections)}/{self.max_clients}")
            return True

    def disconnect(self, websocket: WebSocket):
        self._active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Active clients: {len(self._active_connections)}/{self.max_clients}")

    def broadcast_sync(self, payload: Dict[str, Any]):
        """Thread-safe invocation to broadcast a payload from the background storage thread."""
        self.set_latest_payload(payload)
        if not self._active_connections:
            return

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)

    async def _send_to_client_with_timeout(self, websocket: WebSocket, text_data: str) -> Optional[WebSocket]:
        """Sends data to an individual client with a 1.5-second timeout.
        Returns the websocket if it failed or timed out so it can be evicted without blocking others.
        """
        try:
            # 1.5s timeout prevents a slow/stalled client from blocking broadcast to others
            await asyncio.wait_for(websocket.send_text(text_data), timeout=1.5)
            return None
        except Exception:
            return websocket

    async def broadcast(self, payload: Dict[str, Any]):
        """Sends JSON payload concurrently to all connected clients using isolated per-client tasks."""
        if not self._active_connections:
            return

        text_data = json.dumps(payload)
        connections = list(self._active_connections)

        # Broadcast in parallel to all clients
        results = await asyncio.gather(
            *(self._send_to_client_with_timeout(ws, text_data) for ws in connections),
            return_exceptions=True
        )

        # Discard dead or timed-out connections
        for res in results:
            if isinstance(res, WebSocket):
                self.disconnect(res)

# Global singleton broadcaster instance
broadcaster = TelemetryBroadcaster()
