"""Latency Telemetry API Endpoints (Current & History) - Phase 7"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.schemas.latency import LatencySnapshot, LatencyHistoryResponse
from backend.services.latency_service import latency_service
from backend.database.session import get_db

router = APIRouter()

@router.get("/latency/current", response_model=LatencySnapshot)
def get_current_latency():
    """Returns the latest genuine network probe snapshot including reachability,
    latencies, packet loss, probe age, and staleness flag.
    """
    return latency_service.get_current_latency()

@router.get("/latency/history", response_model=LatencyHistoryResponse)
def get_latency_history(
    target: Optional[str] = Query(None, description="Filter by probe target IP/host"),
    from_ts: Optional[float] = Query(None, alias="from", description="Filter start Unix timestamp"),
    to_ts: Optional[float] = Query(None, alias="to", description="Filter end Unix timestamp"),
    limit: int = Query(120, ge=1, le=1000, description="Max probe records to return"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Order by timestamp: asc or desc"),
    db: Session = Depends(get_db)
):
    """Returns genuine stored probe records from the SQLite latency_metrics table."""
    return latency_service.get_latency_history(
        db=db,
        target=target,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        order=order
    )
