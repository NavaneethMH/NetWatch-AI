# -*- coding: utf-8 -*-
"""Phase 12: Historical Analytics & Reporting — Pydantic Schemas.

Defines response shapes for:
  - /api/analytics/coverage   — per-table data-availability summary
  - /api/analytics/timeseries — downsampled multi-metric time-series
  - /api/analytics/report     — aggregated statistics for a time window
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ─── Coverage ────────────────────────────────────────────────────────────────

class TableCoverage(BaseModel):
    """Row count, time range, and retention info for one SQLite table."""
    table: str
    row_count: int
    oldest_ts: Optional[float] = None
    newest_ts: Optional[float] = None
    oldest_utc: Optional[str] = None
    newest_utc: Optional[str] = None
    span_seconds: Optional[float] = None
    span_human: Optional[str] = None
    retention_seconds: Optional[int] = None
    retention_human: Optional[str] = None


class AnalyticsCoverage(BaseModel):
    """Aggregate data-availability summary for all time-series tables."""
    generated_at_utc: str
    tables: List[TableCoverage]


# ─── Time-Series Aggregation ──────────────────────────────────────────────────

class TimeSeriesPoint(BaseModel):
    """One downsampled bucket of aggregated metrics."""
    bucket_ts: float                        # Bucket start epoch
    bucket_utc: str                         # Bucket start ISO-8601 UTC
    # Network
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    # System
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    # Latency
    latency_avg_ms: Optional[float] = None
    latency_min_ms: Optional[float] = None
    latency_max_ms: Optional[float] = None
    packet_loss_percent: Optional[float] = None
    # Protocol
    pps: Optional[float] = None
    total_packets: Optional[int] = None
    tcp_packets: Optional[int] = None
    udp_packets: Optional[int] = None
    icmp_packets: Optional[int] = None
    dns_packets: Optional[int] = None
    ipv4_packets: Optional[int] = None
    ipv6_packets: Optional[int] = None


class TimeSeriesResponse(BaseModel):
    """Downsampled multi-metric history for the requested range."""
    from_ts: float
    to_ts: float
    from_utc: str
    to_utc: str
    bucket_seconds: int
    point_count: int
    metrics: List[str]                  # Which metric families are present
    points: List[TimeSeriesPoint]


# ─── Aggregate Report ────────────────────────────────────────────────────────

class MetricAggregate(BaseModel):
    """Min / max / avg / p95 aggregate over the requested window."""
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    p95: Optional[float] = None
    sample_count: int = 0


class AnalyticsReport(BaseModel):
    """Aggregated statistics for a selected time window."""
    from_ts: float
    to_ts: float
    from_utc: str
    to_utc: str
    window_seconds: float
    window_human: str
    # Network
    download_mbps: MetricAggregate = Field(default_factory=MetricAggregate)
    upload_mbps: MetricAggregate = Field(default_factory=MetricAggregate)
    # System
    cpu_percent: MetricAggregate = Field(default_factory=MetricAggregate)
    memory_percent: MetricAggregate = Field(default_factory=MetricAggregate)
    # Latency
    latency_avg_ms: MetricAggregate = Field(default_factory=MetricAggregate)
    packet_loss_percent: MetricAggregate = Field(default_factory=MetricAggregate)
    # Protocol
    pps: MetricAggregate = Field(default_factory=MetricAggregate)
    total_packets: int = 0
    tcp_share_pct: Optional[float] = None
    udp_share_pct: Optional[float] = None
    icmp_share_pct: Optional[float] = None
    dns_share_pct: Optional[float] = None
    ipv4_share_pct: Optional[float] = None
    ipv6_share_pct: Optional[float] = None
    # Alert summary
    total_alerts: int = 0
    critical_alerts: int = 0
    warning_alerts: int = 0
    info_alerts: int = 0
