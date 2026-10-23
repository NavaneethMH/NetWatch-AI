# -*- coding: utf-8 -*-
"""Phase 12: Historical Analytics & Reporting — REST API Router.

Endpoints:
  GET /api/analytics/coverage    → per-table data availability
  GET /api/analytics/timeseries  → downsampled multi-metric points
  GET /api/analytics/report      → aggregated window statistics
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from backend.schemas.analytics import (
    AnalyticsCoverage,
    TimeSeriesResponse,
    AnalyticsReport,
)
from backend.services.analytics_service import analytics_service

router = APIRouter()

RANGE_KEYS = {"5m", "15m", "1h", "6h", "24h", "7d", "all"}


@router.get("/analytics/coverage", response_model=AnalyticsCoverage)
def get_analytics_coverage():
    """Returns row counts, time ranges, and retention config for all time-series tables."""
    return analytics_service.get_coverage()


@router.get("/analytics/timeseries", response_model=TimeSeriesResponse)
def get_analytics_timeseries(
    range: str = Query("1h", description="Preset range key: 5m, 15m, 1h, 6h, 24h, 7d, all"),
    from_ts: Optional[float] = Query(None, alias="from", description="Custom start epoch (overrides range)"),
    to_ts: Optional[float] = Query(None, alias="to", description="Custom end epoch (overrides range)"),
    bucket: Optional[int] = Query(None, description="Override bucket duration in seconds"),
    metrics: Optional[List[str]] = Query(None, description="Metric families: network, system, latency, protocol"),
):
    """Returns downsampled multi-metric time-series for the requested time window."""
    if range not in RANGE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range '{range}'. Supported ranges: {sorted(list(RANGE_KEYS))}"
        )
    return analytics_service.get_timeseries(
        range_key=range,
        from_ts=from_ts,
        to_ts=to_ts,
        bucket_seconds=bucket,
        metrics=metrics,
    )


@router.get("/analytics/report", response_model=AnalyticsReport)
def get_analytics_report(
    range: str = Query("24h", description="Preset range key: 5m, 15m, 1h, 6h, 24h, 7d, all"),
    from_ts: Optional[float] = Query(None, alias="from", description="Custom start epoch (overrides range)"),
    to_ts: Optional[float] = Query(None, alias="to", description="Custom end epoch (overrides range)"),
):
    """Returns aggregated statistics (min/max/avg/p95) for the selected window."""
    if range not in RANGE_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range '{range}'. Supported ranges: {sorted(list(RANGE_KEYS))}"
        )
    return analytics_service.get_report(
        range_key=range,
        from_ts=from_ts,
        to_ts=to_ts,
    )
