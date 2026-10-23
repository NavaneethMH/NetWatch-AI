"""Latency Telemetry Schemas (Phase 7)"""
from pydantic import BaseModel, Field
from typing import Optional, List

class LatencySnapshot(BaseModel):
    """Represents the most recent genuine network probe result."""
    probe_id: Optional[str] = None
    target: str
    status: str = "WARMING_UP"  # LIVE, PARTIAL, UNREACHABLE, ERROR, WARMING_UP
    is_reachable: bool = False
    
    packets_sent: int = 0
    packets_received: int = 0
    packet_loss_percent: Optional[float] = None
    
    latency_last_ms: Optional[float] = None
    latency_min_ms: Optional[float] = None
    latency_max_ms: Optional[float] = None
    latency_avg_ms: Optional[float] = None
    
    timestamp: float = 0.0
    timestamp_utc: str = ""
    probe_age_seconds: Optional[float] = None
    is_stale: bool = False

    # Backwards-compatible aliases for existing frontend references
    @property
    def current_latency_ms(self) -> Optional[float]:
        return self.latency_last_ms

    @property
    def min_latency_ms(self) -> Optional[float]:
        return self.latency_min_ms

    @property
    def max_latency_ms(self) -> Optional[float]:
        return self.latency_max_ms

    @property
    def avg_latency_ms(self) -> Optional[float]:
        return self.latency_avg_ms

class LatencyHistoryItem(BaseModel):
    id: int
    probe_id: str
    timestamp: float
    timestamp_utc: str
    target: str
    status: str
    is_reachable: bool
    packets_sent: int
    packets_received: int
    packet_loss_percent: Optional[float] = None
    latency_last_ms: Optional[float] = None
    latency_min_ms: Optional[float] = None
    latency_max_ms: Optional[float] = None
    latency_avg_ms: Optional[float] = None

class LatencyHistoryResponse(BaseModel):
    target: Optional[str] = None
    count: int
    limit: int
    items: List[LatencyHistoryItem]
