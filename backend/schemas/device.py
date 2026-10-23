# -*- coding: utf-8 -*-
"""Device Discovery Pydantic Schemas (Phase 9)"""
from pydantic import BaseModel
from typing import Optional, List


class DeviceItem(BaseModel):
    """Single discovered LAN device record."""
    id: int
    mac_address: Optional[str] = None
    ip_address: str
    hostname: Optional[str] = None
    interface_name: str
    first_seen: float
    first_seen_utc: str
    last_seen: float
    last_seen_utc: str
    status: str          # ONLINE / OFFLINE / UNKNOWN
    missed_scan_count: int

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    """Paginated list of known LAN devices."""
    count: int
    total: int
    items: List[DeviceItem]


class DiscoveryStatus(BaseModel):
    """Current state of the device discovery worker."""
    status: str                     # IDLE / SCANNING / ERROR / UNAVAILABLE
    discovery_method: str           # e.g. "arp_table+icmp_sweep"
    interface: Optional[str]        # e.g. "Wi-Fi"
    subnet: Optional[str]           # e.g. "192.168.31.0/24"
    last_scan_utc: Optional[str]
    last_scan_duration_seconds: Optional[float]
    devices_found_last_scan: Optional[int]
    limitation: Optional[str]       # human-readable note when method is degraded
    error: Optional[str]            # set when status == ERROR


class DeviceSummary(BaseModel):
    """Lightweight device summary for WebSocket payload (Phase 9)."""
    online: int
    known: int
    discovery_status: str
    last_scan_utc: Optional[str]
