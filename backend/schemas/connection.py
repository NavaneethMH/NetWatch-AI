# -*- coding: utf-8 -*-
"""Active Connection Schemas (Phase 10)

Strictly typed models for genuine local host connection inspection.
No fabricated or simulated values.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ConnectionItem(BaseModel):
    """Represents a single active network connection on the host."""
    id: str = Field(..., description="Stable runtime identifier")
    protocol: str = Field(..., description="TCP or UDP")
    local_ip: Optional[str] = None
    local_port: Optional[int] = None
    remote_ip: Optional[str] = None
    remote_port: Optional[int] = None
    state: str = Field(..., description="Connection status (e.g. ESTABLISHED, LISTEN, NONE)")
    family: str = Field(..., description="IPv4 or IPv6")
    pid: Optional[int] = None
    process_name: Optional[str] = None
    first_observed: float
    first_observed_utc: str
    last_observed: float
    last_observed_utc: str


class ConnectionListResponse(BaseModel):
    """Filtered list of active connections."""
    count: int
    total: int
    items: List[ConnectionItem]


class ConnectionSummary(BaseModel):
    """Lightweight summary of active connections for WebSocket broadcasting and dashboard KPIs."""
    total: int = 0
    tcp: int = 0
    udp: int = 0
    established: int = 0
    listening: int = 0
    time_wait: int = 0
    close_wait: int = 0
    other: int = 0
    last_scan_utc: Optional[str] = None
    scan_duration_ms: Optional[float] = None
