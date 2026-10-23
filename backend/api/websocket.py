"""WebSocket Telemetry Endpoint (Phase 5)"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.broadcaster import broadcaster
from backend.services.system_service import system_service
from backend.services.network_service import network_service
from backend.collectors.latency import latency_collector
from backend.services.alert_service import alert_service
from backend.services.health_score_service import health_score_service
from datetime import datetime, timezone
import logging

logger = logging.getLogger("netwatch.ws")
router = APIRouter()

@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """Real-time live telemetry stream.
    Accepts client connection, immediately sends the latest genuine cached snapshot (or current state)
    with type='snapshot' and reuses the real sample_id, then streams live updates.
    """
    accepted = await broadcaster.connect(websocket)
    if not accepted:
        return
    
    # 1. Provide initial snapshot reusing the latest real sample_id if available
    try:
        latest = broadcaster.get_latest_payload()
        if latest:
            snapshot_payload = dict(latest)
            snapshot_payload["type"] = "snapshot"
        else:
            sys_snap = system_service.get_current_system_telemetry()
            net_snap = network_service.get_current_network_throughput()
            lat_snap = latency_collector.collect()
            alert_summary = alert_service.get_summary()
            health_score = health_score_service.calculate_score(sys_snap, net_snap, lat_snap, alert_summary)
            snapshot_payload = {
                "type": "snapshot",
                "sample_id": "initial-bootstrap",
                "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "system": sys_snap.model_dump(),
                "network": net_snap.model_dump(),
                "latency": lat_snap.model_dump(),
                "health_score": health_score.model_dump(),
                "alerts_summary": alert_summary.model_dump()
            }
        await websocket.send_json(snapshot_payload)
    except Exception as e:
        logger.warning(f"Failed to send initial telemetry snapshot: {e}")

    try:
        while True:
            # Keep connection open; receive client pings/messages if sent
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception as e:
        logger.info(f"WebSocket closed: {e}")
        broadcaster.disconnect(websocket)
