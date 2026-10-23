"""Network Health Score API Endpoint (Phase 8)"""
from fastapi import APIRouter
from backend.services.system_service import system_service
from backend.services.network_service import network_service
from backend.collectors.latency import latency_collector
from backend.services.health_score_service import health_score_service
from backend.schemas.health_score import HealthScoreResponse

router = APIRouter()

@router.get("/health-score", response_model=HealthScoreResponse)
def get_health_score():
    """Returns the deterministic 0-100 network health score computed from current live telemetry snapshots."""
    sys_snap = system_service.get_current_system_telemetry()
    net_snap = network_service.get_current_network_throughput()
    lat_snap = latency_collector.collect()
    return health_score_service.calculate_score(sys_snap, net_snap, lat_snap)
