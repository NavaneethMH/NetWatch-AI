"""Pydantic schemas for System, Network, and Interface History APIs (Phase 4)"""
from pydantic import BaseModel, Field
from typing import List, Optional

class SystemHistoryItem(BaseModel):
    id: int
    sample_id: str
    timestamp: float
    timestamp_utc: str
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used_bytes: Optional[int] = None
    memory_total_bytes: Optional[int] = None
    disk_percent: Optional[float] = None
    disk_used_bytes: Optional[int] = None
    disk_total_bytes: Optional[int] = None
    uptime_seconds: Optional[float] = None
    collector_status: str
    unavailable_fields: Optional[str] = None

class SystemHistoryResponse(BaseModel):
    count: int
    limit: int
    items: List[SystemHistoryItem]

class NetworkHistoryItem(BaseModel):
    id: int
    sample_id: str
    timestamp: float
    timestamp_utc: str
    status: str
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    bytes_recv: int
    bytes_sent: int
    packets_recv: int
    packets_sent: int
    elapsed_seconds: Optional[float] = None

class NetworkHistoryResponse(BaseModel):
    count: int
    limit: int
    items: List[NetworkHistoryItem]

class InterfaceHistoryItem(BaseModel):
    id: int
    sample_id: str
    timestamp: float
    timestamp_utc: str
    interface_name: str
    is_up: bool
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    bytes_recv: int
    bytes_sent: int
    packets_recv: int
    packets_sent: int

class InterfaceHistoryResponse(BaseModel):
    interface_name: str
    count: int
    limit: int
    items: List[InterfaceHistoryItem]
