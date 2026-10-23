"""Alert Schemas (Phase 8)"""
from typing import Optional, List
from pydantic import BaseModel, Field

class AlertItem(BaseModel):
    id: int
    alert_id: str
    type: str
    severity: str
    status: str
    source: str
    message: str
    metric_name: str
    observed_value: Optional[float] = None
    threshold_value: Optional[float] = None
    opened_at: float
    opened_at_utc: str
    acknowledged_at: Optional[float] = None
    acknowledged_at_utc: Optional[str] = None
    resolved_at: Optional[float] = None
    resolved_at_utc: Optional[str] = None
    last_seen_at: float
    last_seen_at_utc: str
    occurrence_count: int

class AlertListResponse(BaseModel):
    total: int
    count: int
    items: List[AlertItem]

class AlertSummary(BaseModel):
    total_active: int
    open_count: int
    acknowledged_count: int
    critical_count: int
    warning_count: int
    info_count: int

class AlertAcknowledgeResponse(BaseModel):
    success: bool
    message: str
    alert: AlertItem
