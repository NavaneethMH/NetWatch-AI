# -*- coding: utf-8 -*-
"""Active Connection API Endpoints (Phase 10).

Exposes real host network connections and lightweight summary.
Reads from in-memory state; never triggers an OS connection scan.
"""
from typing import Optional
from fastapi import APIRouter, Query

from backend.schemas.connection import ConnectionListResponse, ConnectionSummary
from backend.services.connection_service import connection_service

router = APIRouter()


@router.get("/connections", response_model=ConnectionListResponse)
def list_connections(
    protocol: Optional[str] = Query(None, description="Filter by protocol: TCP, UDP"),
    state: Optional[str] = Query(None, description="Filter by state: ESTABLISHED, LISTEN, TIME_WAIT, etc."),
    process: Optional[str] = Query(None, description="Filter by process name substring"),
    search: Optional[str] = Query(None, description="Search across IP, port, process name, PID, state"),
    limit: int = Query(200, ge=1, le=1000, description="Max items to return"),
):
    """Returns active network connections from current in-memory state.
    Does NOT invoke psutil.net_connections() directly.
    """
    return connection_service.get_connections(
        protocol=protocol,
        state=state,
        process=process,
        search=search,
        limit=limit,
    )


@router.get("/connections/summary", response_model=ConnectionSummary)
def get_connection_summary():
    """Returns lightweight connection counters (total, tcp, udp, established, listening, etc.).
    Does NOT trigger an OS scan.
    """
    return connection_service.get_summary()
