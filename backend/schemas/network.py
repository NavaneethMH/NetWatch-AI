"""Pydantic schemas for Network Telemetry and Throughput (Phase 3)"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import time
from datetime import datetime, timezone

def get_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class InterfaceThroughput(BaseModel):
    name: str
    is_up: bool
    download_mbps: Optional[float] = Field(None, description="Interface download Mbps (None if warming up)")
    upload_mbps: Optional[float] = Field(None, description="Interface upload Mbps (None if warming up)")
    bytes_recv: int
    bytes_sent: int
    packets_recv: int
    packets_sent: int

class NetworkThroughputResponse(BaseModel):
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of collection")
    timestamp_iso: str = Field(default_factory=get_utc_iso, description="UTC ISO 8601 timestamp")
    status: str = Field("LIVE", description="Status: LIVE, WARMING_UP, or DEGRADED")
    download_mbps: Optional[float] = Field(None, description="Aggregate download Mbps (None if warming up)")
    upload_mbps: Optional[float] = Field(None, description="Aggregate upload Mbps (None if warming up)")
    bytes_recv_total: int = Field(..., description="Cumulative total bytes received across all interfaces")
    bytes_sent_total: int = Field(..., description="Cumulative total bytes sent across all interfaces")
    packets_recv_total: int = Field(..., description="Cumulative total packets received across all interfaces")
    packets_sent_total: int = Field(..., description="Cumulative total packets sent across all interfaces")
    sample_interval_seconds: Optional[float] = Field(None, description="Elapsed monotonic seconds between successive counter samples")
    interfaces: List[InterfaceThroughput] = Field(default_factory=list, description="Per-interface throughput metrics")
