"""Network Telemetry API Endpoints (Current & History)"""
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from typing import Optional
from backend.schemas.network import NetworkThroughputResponse
from backend.schemas.history import NetworkHistoryResponse, InterfaceHistoryResponse
from backend.services.network_service import network_service
from backend.services.history_service import history_service
from backend.database.session import get_db

router = APIRouter()

@router.get("/network/current", response_model=NetworkThroughputResponse)
def get_current_network():
    """Returns genuine real-time upload/download Mbps calculated from byte-counter deltas."""
    return network_service.get_current_network_throughput()

@router.get("/network/history", response_model=NetworkHistoryResponse)
def get_network_history(
    start_time: Optional[float] = Query(None, description="Start Unix timestamp filter"),
    end_time: Optional[float] = Query(None, description="End Unix timestamp filter"),
    limit: int = Query(120, ge=1, le=1000, description="Max samples to return"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Order by timestamp: asc or desc"),
    db: Session = Depends(get_db)
):
    """Returns stored historical aggregate network throughput and counters from SQLite."""
    return history_service.get_network_history(db, start_time, end_time, limit, order)

@router.get("/network/interfaces/{interface_name}/history", response_model=InterfaceHistoryResponse)
def get_interface_history(
    interface_name: str = Path(..., description="Name of the interface, e.g. Wi-Fi"),
    start_time: Optional[float] = Query(None, description="Start Unix timestamp filter"),
    end_time: Optional[float] = Query(None, description="End Unix timestamp filter"),
    limit: int = Query(120, ge=1, le=1000, description="Max samples to return"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Order by timestamp: asc or desc"),
    db: Session = Depends(get_db)
):
    """Returns stored historical per-interface throughput and counters from SQLite."""
    return history_service.get_interface_history(db, interface_name, start_time, end_time, limit, order)
