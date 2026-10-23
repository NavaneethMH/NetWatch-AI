"""Pydantic schemas for System and Network Interface Telemetry (Phase 2 & 3)"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import time
from datetime import datetime, timezone

def get_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class CpuMetrics(BaseModel):
    usage_percent: Optional[float] = Field(None, description="Current system-wide CPU utilization percentage (None if priming)")
    is_ready: bool = Field(True, description="Whether CPU sampling has completed priming")
    core_count_logical: Optional[int] = Field(None, description="Number of logical CPU cores")
    core_count_physical: Optional[int] = Field(None, description="Number of physical CPU cores")

class MemoryMetrics(BaseModel):
    usage_percent: float = Field(..., description="RAM utilization percentage")
    total_bytes: int = Field(..., description="Total physical RAM in bytes")
    used_bytes: int = Field(..., description="Used physical RAM in bytes")
    available_bytes: int = Field(..., description="Available physical RAM in bytes")

class DiskMetrics(BaseModel):
    usage_percent: float = Field(..., description="Root/primary drive disk utilization percentage")
    total_bytes: int = Field(..., description="Total disk capacity in bytes")
    used_bytes: int = Field(..., description="Used disk capacity in bytes")
    free_bytes: int = Field(..., description="Free disk capacity in bytes")
    mount_point: str = Field(..., description="Mount point or drive letter inspected")

class InterfaceAddress(BaseModel):
    family: str
    address: str
    netmask: Optional[str] = None
    broadcast: Optional[str] = None

class InterfaceInfo(BaseModel):
    name: str
    is_up: bool
    speed_mbps: Optional[int] = None
    mtu: Optional[int] = None
    addresses: List[InterfaceAddress] = []

class NetworkTotals(BaseModel):
    bytes_sent: int = Field(..., description="Cumulative total bytes sent across all interfaces")
    bytes_recv: int = Field(..., description="Cumulative total bytes received across all interfaces")
    packets_sent: int = Field(..., description="Cumulative total packets sent across all interfaces")
    packets_recv: int = Field(..., description="Cumulative total packets received across all interfaces")
    errin: int = Field(0, description="Cumulative inbound errors")
    errout: int = Field(0, description="Cumulative outbound errors")
    dropin: int = Field(0, description="Cumulative inbound dropped packets")
    dropout: int = Field(0, description="Cumulative outbound dropped packets")

class SystemTelemetryResponse(BaseModel):
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of collection")
    timestamp_iso: str = Field(default_factory=get_utc_iso, description="UTC ISO 8601 timestamp")
    system_uptime_seconds: float = Field(..., description="Host OS uptime in seconds")
    boot_time_timestamp: float = Field(..., description="Host boot time timestamp")
    cpu: CpuMetrics
    memory: MemoryMetrics
    disk: DiskMetrics
    network_totals: NetworkTotals
    interfaces: List[InterfaceInfo]
    collector_status: str = Field("OK", description="Status of the psutil collector")
    unavailable_fields: List[str] = Field(default_factory=list, description="Fields that could not be read or require permissions")
