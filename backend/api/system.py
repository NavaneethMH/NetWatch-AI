"""System Telemetry API Endpoints (Current & History)"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from backend.schemas.system import SystemTelemetryResponse
from backend.schemas.history import SystemHistoryResponse
from backend.services.system_service import system_service
from backend.services.history_service import history_service
from backend.database.session import get_db

router = APIRouter()

@router.get("/system/current", response_model=SystemTelemetryResponse)
def get_current_system():
    """Returns genuine, real-time host hardware and network counter telemetry."""
    return system_service.get_current_system_telemetry()

@router.get("/system/history", response_model=SystemHistoryResponse)
def get_system_history(
    start_time: Optional[float] = Query(None, description="Start Unix timestamp filter"),
    end_time: Optional[float] = Query(None, description="End Unix timestamp filter"),
    limit: int = Query(120, ge=1, le=1000, description="Max samples to return"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Order by timestamp: asc or desc"),
    db: Session = Depends(get_db)
):
    """Returns stored historical system hardware metrics from SQLite."""
    return history_service.get_system_history(db, start_time, end_time, limit, order)
