# -*- coding: utf-8 -*-
"""Device Discovery API Endpoints (Phase 9)"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from backend.services.device_service import device_service
from backend.schemas.device import DeviceListResponse, DeviceItem, DiscoveryStatus

router = APIRouter()


@router.get("/devices", response_model=DeviceListResponse)
def list_devices(
    status: Optional[str] = Query(None, description="Filter by status: ONLINE, OFFLINE, UNKNOWN"),
    search: Optional[str] = Query(None, description="Search by IP, MAC, or hostname"),
    limit: int = Query(200, ge=1, le=1000, description="Max devices to return"),
):
    """Returns all known LAN devices from the persistent devices table.
    Does NOT trigger a new scan. Devices persist across backend restarts.
    """
    return device_service.get_devices(status=status, search=search, limit=limit)


@router.get("/devices/discovery/status", response_model=DiscoveryStatus)
def get_discovery_status():
    """Returns current state of the device discovery worker:
    IDLE / SCANNING / ERROR / UNAVAILABLE, plus subnet and method info.
    """
    return device_service.get_discovery_status()


from backend.core.security import require_operator_auth
from backend.core.config import settings

# Process-level last manual scan timestamp — reset on each worker restart.
# Thread safety: FastAPI handlers run in the same thread for sync routes; atomicity
# is sufficient because the background sweep thread only writes its own _scanning flag.
_last_manual_scan_ts: float = 0.0


@router.post("/devices/scan")
def trigger_scan(
    _auth: bool = Depends(require_operator_auth),
    response: "Response" = None,  # type: ignore[assignment]
):
    """Manually trigger an immediate discovery scan.

    Rate-limited to one manual trigger per DEVICE_SCAN_COOLDOWN_SECONDS (default 60 s).
    If a scan is already in progress the existing state is returned without launching another.
    Requires operator authorization when configured.
    """
    import time
    from fastapi import Response
    from fastapi.responses import JSONResponse

    global _last_manual_scan_ts
    now = time.time()
    elapsed = now - _last_manual_scan_ts
    cooldown = settings.DEVICE_SCAN_COOLDOWN_SECONDS

    if elapsed < cooldown:
        retry_after = int(cooldown - elapsed) + 1
        return JSONResponse(
            status_code=429,
            content={
                "detail": (
                    f"Manual scan rate-limited. "
                    f"Wait {retry_after}s before triggering another scan."
                ),
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    started = device_service.trigger_manual_scan()
    if started:
        _last_manual_scan_ts = now

    status = device_service.get_discovery_status()
    return {
        "started": started,
        "message": "Scan started." if started else "Scan already in progress.",
        "current_status": status.status,
    }


@router.get("/devices/{device_id}", response_model=DeviceItem)
def get_device(device_id: int):
    """Returns a single device record by database ID."""
    device = device_service.get_device_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device
