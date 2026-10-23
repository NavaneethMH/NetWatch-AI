"""Alert API Endpoints (Phase 8)"""
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.database.alert_repository import alert_repo
from backend.schemas.alert import (
    AlertItem,
    AlertListResponse,
    AlertSummary,
    AlertAcknowledgeResponse
)

router = APIRouter()

def _model_to_schema(a) -> AlertItem:
    return AlertItem(
        id=a.id,
        alert_id=a.alert_id,
        type=a.type,
        severity=a.severity,
        status=a.status,
        source=a.source,
        message=a.message,
        metric_name=a.metric_name,
        observed_value=a.observed_value,
        threshold_value=a.threshold_value,
        opened_at=a.opened_at,
        opened_at_utc=a.opened_at_utc,
        acknowledged_at=a.acknowledged_at,
        acknowledged_at_utc=a.acknowledged_at_utc,
        resolved_at=a.resolved_at,
        resolved_at_utc=a.resolved_at_utc,
        last_seen_at=a.last_seen_at,
        last_seen_at_utc=a.last_seen_at_utc,
        occurrence_count=a.occurrence_count
    )

@router.get("/alerts", response_model=AlertListResponse)
def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, ACKNOWLEDGED, RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO, WARNING, CRITICAL)"),
    type: Optional[str] = Query(None, description="Filter by alert type"),
    limit: int = Query(100, ge=1, le=1000, description="Max alerts to return"),
    db: Session = Depends(get_db)
):
    """Retrieves persisted alerts from SQLite with optional filtering."""
    alerts = alert_repo.list_alerts(
        db=db,
        status=status,
        severity=severity,
        alert_type=type,
        limit=limit
    )
    items = [_model_to_schema(a) for a in alerts]
    return AlertListResponse(
        total=len(items),
        count=len(items),
        items=items
    )

@router.get("/alerts/summary", response_model=AlertSummary)
def get_alerts_summary(db: Session = Depends(get_db)):
    """Retrieves count of active alerts grouped by status and severity."""
    return alert_repo.get_active_summary(db)

@router.get("/alerts/{identifier}", response_model=AlertItem)
def get_alert_by_id(identifier: str, db: Session = Depends(get_db)):
    """Retrieves a single alert by numeric ID or UUID alert_id."""
    alert = alert_repo.get_alert_by_id(db, identifier)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _model_to_schema(alert)

from backend.core.security import require_operator_auth

@router.post("/alerts/{identifier}/acknowledge", response_model=AlertAcknowledgeResponse)
def acknowledge_alert(
    identifier: str,
    db: Session = Depends(get_db),
    _auth: bool = Depends(require_operator_auth)
):
    """Acknowledges an active alert.
    Marks status as ACKNOWLEDGED. Acknowledging registers operator awareness without resolving the condition.
    Requires operator authorization when configured.
    """
    now_ts = time.time()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alert = alert_repo.acknowledge_alert(db, identifier, now_ts, now_iso)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertAcknowledgeResponse(
        success=True,
        message=f"Alert {alert.type} ({alert.alert_id}) acknowledged successfully",
        alert=_model_to_schema(alert)
    )
