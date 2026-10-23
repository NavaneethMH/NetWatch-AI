# -*- coding: utf-8 -*-
"""Protocol and Packet Analytics API Endpoints (Phase 11).

Exposes current protocol window and historical aggregated protocol statistics.
Queries read from in-memory state or SQLite; requests never trigger packet capture.
"""
from typing import Optional
from fastapi import APIRouter, Query

from backend.schemas.protocol import ProtocolHistoryResponse, ProtocolWindowMetric
from backend.services.protocol_service import protocol_service

router = APIRouter()


@router.get("/protocols/current", response_model=ProtocolWindowMetric)
def get_current_protocol_window():
    """Returns the latest aggregated packet and protocol statistics window.
    Does NOT invoke packet sniffing.
    """
    return protocol_service.get_current()


@router.get("/protocols/history", response_model=ProtocolHistoryResponse)
def get_protocol_history(
    from_ts: Optional[float] = Query(None, alias="from", description="Start timestamp (epoch seconds)"),
    to_ts: Optional[float] = Query(None, alias="to", description="End timestamp (epoch seconds)"),
    limit: int = Query(50, ge=1, le=500, description="Max history windows to return"),
):
    """Returns aggregated time-window history from SQLite."""
    return protocol_service.get_history(from_ts=from_ts, to_ts=to_ts, limit=limit)
