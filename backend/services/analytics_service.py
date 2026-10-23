# -*- coding: utf-8 -*-
"""Phase 12: Historical Analytics & Reporting — Service Layer.

Provides:
  - get_coverage()         → per-table data availability summary
  - get_timeseries()       → downsampled multi-metric points
  - get_report()           → aggregated statistics for a time window

All queries run read-only against SQLite via raw SQL for performance;
SQLAlchemy ORM is intentionally bypassed here to support GROUP BY / percentile math.
"""
from __future__ import annotations

import math
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Sequence

from backend.database.session import engine
from backend.schemas.analytics import (
    AnalyticsCoverage,
    AnalyticsReport,
    MetricAggregate,
    TableCoverage,
    TimeSeriesPoint,
    TimeSeriesResponse,
)
from backend.core.config import settings


# ─── helpers ─────────────────────────────────────────────────────────────────

def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _human_span(seconds: float) -> str:
    if seconds < 120:
        return f"{int(seconds)}s"
    if seconds < 7200:
        return f"{seconds / 60:.1f}m"
    if seconds < 172800:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _percentile(sorted_vals: list, pct: float) -> Optional[float]:
    if not sorted_vals:
        return None
    idx = (pct / 100) * (len(sorted_vals) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _aggregate(vals: list) -> MetricAggregate:
    clean = [v for v in vals if v is not None]
    if not clean:
        return MetricAggregate(sample_count=0)
    clean.sort()
    return MetricAggregate(
        min=round(min(clean), 4),
        max=round(max(clean), 4),
        avg=round(sum(clean) / len(clean), 4),
        p95=round(_percentile(clean, 95), 4),
        sample_count=len(clean),
    )


def _raw_conn() -> sqlite3.Connection:
    """Open a direct read-only SQLite connection bypassing SQLAlchemy."""
    db_path = engine.url.database
    if not db_path:
        db_url: str = str(engine.url)
        db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Retention lookup ────────────────────────────────────────────────────────

_RETENTION_MAP: dict[str, int] = {
    "system_metrics":   getattr(settings, "RETENTION_SYSTEM_SECONDS", 7 * 86400),
    "network_metrics":  getattr(settings, "RETENTION_NETWORK_SECONDS", 7 * 86400),
    "interface_metrics": getattr(settings, "RETENTION_IFACE_SECONDS", 7 * 86400),
    "latency_metrics":  getattr(settings, "RETENTION_LATENCY_SECONDS", 7 * 86400),
    "protocol_metrics": getattr(settings, "RETENTION_PROTOCOL_SECONDS", 7 * 86400),
    "alerts":           getattr(settings, "RETENTION_ALERT_SECONDS", 30 * 86400),
    "devices":          None,   # no expiry
}


# ─── Public API ──────────────────────────────────────────────────────────────

def get_coverage() -> AnalyticsCoverage:
    """Return per-table row counts, time ranges, and retention config."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tables_out: list[TableCoverage] = []

    conn = _raw_conn()
    try:
        cur = conn.cursor()
        for table, retention in _RETENTION_MAP.items():
            try:
                cur.execute(
                    f"SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM {table}"  # noqa: S608
                )
                row = cur.fetchone()
                count = row[0] or 0
                oldest = row[1]
                newest = row[2]
                span = (newest - oldest) if (oldest and newest) else None
                tables_out.append(
                    TableCoverage(
                        table=table,
                        row_count=count,
                        oldest_ts=oldest,
                        newest_ts=newest,
                        oldest_utc=_utc(oldest) if oldest else None,
                        newest_utc=_utc(newest) if newest else None,
                        span_seconds=round(span, 1) if span else None,
                        span_human=_human_span(span) if span else None,
                        retention_seconds=retention,
                        retention_human=_human_span(retention) if retention else "unlimited",
                    )
                )
            except sqlite3.OperationalError:
                # Table might not exist yet (e.g. fresh install)
                tables_out.append(TableCoverage(table=table, row_count=0))
    finally:
        conn.close()

    return AnalyticsCoverage(generated_at_utc=now_utc, tables=tables_out)


# ─── Time-series ─────────────────────────────────────────────────────────────

_DEFAULT_BUCKET_SECONDS: dict[str, int] = {
    "5m":   10,
    "15m":  30,
    "1h":   60,
    "6h":   300,
    "24h":  900,
    "7d":   3600,
    "all":  3600,
}


def _resolve_window(range_key: str, from_ts: Optional[float], to_ts: Optional[float]):
    now = time.time()
    _map = {
        "5m": 300, "15m": 900, "1h": 3600,
        "6h": 21600, "24h": 86400, "7d": 604800,
    }
    if from_ts is not None and to_ts is not None:
        return from_ts, to_ts
    if range_key == "all":
        # Check actual oldest record across all telemetry tables in db or default to retention policy
        retention_days = getattr(settings, "TELEMETRY_RETENTION_DAYS", 7)
        max_span = max(retention_days * 86400, 7 * 86400)
        try:
            conn = _raw_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT MIN(min_ts) FROM (
                    SELECT MIN(timestamp) as min_ts FROM network_metrics
                    UNION ALL
                    SELECT MIN(timestamp) as min_ts FROM protocol_metrics
                    UNION ALL
                    SELECT MIN(timestamp) as min_ts FROM system_metrics
                ) WHERE min_ts IS NOT NULL AND min_ts > 0
            """)
            row = cur.fetchone()
            oldest = row[0] if row else None
            conn.close()
            if oldest and oldest > 0:
                return float(oldest), now
        except Exception:
            pass
        return now - max_span, now
    span = _map.get(range_key, 86400)
    return now - span, now


def get_timeseries(
    range_key: str = "1h",
    from_ts: Optional[float] = None,
    to_ts: Optional[float] = None,
    bucket_seconds: Optional[int] = None,
    metrics: Optional[List[str]] = None,
) -> TimeSeriesResponse:
    """Return downsampled multi-metric time-series for the requested window."""
    start, end = _resolve_window(range_key, from_ts, to_ts)
    window_span = end - start

    if bucket_seconds is None:
        bucket_seconds = _DEFAULT_BUCKET_SECONDS.get(range_key, 60)
        # Auto-scale: aim for ~120 buckets max
        ideal = max(10, int(window_span / 120))
        bucket_seconds = max(bucket_seconds, ideal)

    want = set(metrics) if metrics else {"network", "system", "latency", "protocol"}

    conn = _raw_conn()
    try:
        buckets: dict[int, dict] = {}

        def _bucket_key(ts: float) -> int:
            return int(ts // bucket_seconds) * bucket_seconds

        # ── Network ──────────────────────────────────────────────────────────
        if "network" in want:
            cur = conn.execute(
                """
                SELECT timestamp, download_mbps, upload_mbps
                FROM network_metrics
                WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'
                ORDER BY timestamp ASC
                """,
                (start, end),
            )
            for row in cur.fetchall():
                k = _bucket_key(row["timestamp"])
                b = buckets.setdefault(k, {})
                b.setdefault("_dl", []).append(row["download_mbps"])
                b.setdefault("_ul", []).append(row["upload_mbps"])

        # ── System ───────────────────────────────────────────────────────────
        if "system" in want:
            cur = conn.execute(
                """
                SELECT timestamp, cpu_percent, memory_percent
                FROM system_metrics
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                (start, end),
            )
            for row in cur.fetchall():
                k = _bucket_key(row["timestamp"])
                b = buckets.setdefault(k, {})
                b.setdefault("_cpu", []).append(row["cpu_percent"])
                b.setdefault("_mem", []).append(row["memory_percent"])

        # ── Latency ──────────────────────────────────────────────────────────
        if "latency" in want:
            cur = conn.execute(
                """
                SELECT timestamp, latency_avg_ms, latency_min_ms, latency_max_ms, packet_loss_percent
                FROM latency_metrics
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                (start, end),
            )
            for row in cur.fetchall():
                k = _bucket_key(row["timestamp"])
                b = buckets.setdefault(k, {})
                b.setdefault("_lat_avg", []).append(row["latency_avg_ms"])
                b.setdefault("_lat_min", []).append(row["latency_min_ms"])
                b.setdefault("_lat_max", []).append(row["latency_max_ms"])
                b.setdefault("_loss", []).append(row["packet_loss_percent"])

        # ── Protocol ─────────────────────────────────────────────────────────
        if "protocol" in want:
            cur = conn.execute(
                """
                SELECT timestamp, packets_per_second, total_packets,
                       tcp_packets, udp_packets, icmp_packets, dns_packets,
                       ipv4_packets, ipv6_packets
                FROM protocol_metrics
                WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'
                ORDER BY timestamp ASC
                """,
                (start, end),
            )
            for row in cur.fetchall():
                k = _bucket_key(row["timestamp"])
                b = buckets.setdefault(k, {})
                b.setdefault("_pps", []).append(row["packets_per_second"])
                b.setdefault("_tp", []).append(row["total_packets"])
                b.setdefault("_tcp", []).append(row["tcp_packets"])
                b.setdefault("_udp", []).append(row["udp_packets"])
                b.setdefault("_icmp", []).append(row["icmp_packets"])
                b.setdefault("_dns", []).append(row["dns_packets"])
                b.setdefault("_ipv4", []).append(row["ipv4_packets"])
                b.setdefault("_ipv6", []).append(row["ipv6_packets"])

    finally:
        conn.close()

    def _avg(lst):
        clean = [v for v in lst if v is not None]
        return round(sum(clean) / len(clean), 4) if clean else None

    def _sum(lst):
        clean = [v for v in lst if v is not None]
        return sum(clean) if clean else None

    points: list[TimeSeriesPoint] = []
    for k in sorted(buckets.keys()):
        b = buckets[k]
        points.append(TimeSeriesPoint(
            bucket_ts=float(k),
            bucket_utc=_utc(float(k)),
            download_mbps=_avg(b.get("_dl", [])),
            upload_mbps=_avg(b.get("_ul", [])),
            cpu_percent=_avg(b.get("_cpu", [])),
            memory_percent=_avg(b.get("_mem", [])),
            latency_avg_ms=_avg(b.get("_lat_avg", [])),
            latency_min_ms=_avg(b.get("_lat_min", [])),
            latency_max_ms=_avg(b.get("_lat_max", [])),
            packet_loss_percent=_avg(b.get("_loss", [])),
            pps=_avg(b.get("_pps", [])),
            total_packets=_sum(b.get("_tp", [])),
            tcp_packets=_sum(b.get("_tcp", [])),
            udp_packets=_sum(b.get("_udp", [])),
            icmp_packets=_sum(b.get("_icmp", [])),
            dns_packets=_sum(b.get("_dns", [])),
            ipv4_packets=_sum(b.get("_ipv4", [])),
            ipv6_packets=_sum(b.get("_ipv6", [])),
        ))

    active_metrics = list(want)
    return TimeSeriesResponse(
        from_ts=start,
        to_ts=end,
        from_utc=_utc(start),
        to_utc=_utc(end),
        bucket_seconds=bucket_seconds,
        point_count=len(points),
        metrics=active_metrics,
        points=points,
    )


# ─── Aggregate Report ────────────────────────────────────────────────────────

def get_report(
    range_key: str = "24h",
    from_ts: Optional[float] = None,
    to_ts: Optional[float] = None,
) -> AnalyticsReport:
    """Return aggregated stats for the selected window."""
    start, end = _resolve_window(range_key, from_ts, to_ts)
    window_span = end - start

    conn = _raw_conn()
    try:
        # Network
        cur = conn.execute(
            "SELECT download_mbps, upload_mbps FROM network_metrics "
            "WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'",
            (start, end),
        )
        rows = cur.fetchall()
        dl_vals = [r["download_mbps"] for r in rows]
        ul_vals = [r["upload_mbps"] for r in rows]

        # System
        cur = conn.execute(
            "SELECT cpu_percent, memory_percent FROM system_metrics "
            "WHERE timestamp >= ? AND timestamp <= ?",
            (start, end),
        )
        rows = cur.fetchall()
        cpu_vals = [r["cpu_percent"] for r in rows]
        mem_vals = [r["memory_percent"] for r in rows]

        # Latency
        cur = conn.execute(
            "SELECT latency_avg_ms, packet_loss_percent FROM latency_metrics "
            "WHERE timestamp >= ? AND timestamp <= ?",
            (start, end),
        )
        rows = cur.fetchall()
        lat_vals = [r["latency_avg_ms"] for r in rows]
        loss_vals = [r["packet_loss_percent"] for r in rows]

        # Protocol
        cur = conn.execute(
            """
            SELECT SUM(total_packets) as total_p,
                   SUM(tcp_packets) as tcp_p,
                   SUM(udp_packets) as udp_p,
                   SUM(icmp_packets) as icmp_p,
                   SUM(dns_packets) as dns_p,
                   SUM(ipv4_packets) as ipv4_p,
                   SUM(ipv6_packets) as ipv6_p
            FROM protocol_metrics
            WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'
            """,
            (start, end),
        )
        proto_agg = cur.fetchone()

        cur2 = conn.execute(
            "SELECT packets_per_second FROM protocol_metrics "
            "WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'",
            (start, end),
        )
        pps_vals = [r["packets_per_second"] for r in cur2.fetchall()]

        total_p = int(proto_agg["total_p"] or 0)
        tcp_p = int(proto_agg["tcp_p"] or 0)
        udp_p = int(proto_agg["udp_p"] or 0)
        icmp_p = int(proto_agg["icmp_p"] or 0)
        dns_p = int(proto_agg["dns_p"] or 0)
        ipv4_p = int(proto_agg["ipv4_p"] or 0)
        ipv6_p = int(proto_agg["ipv6_p"] or 0)

        def _pct(num, denom):
            return round(100 * num / denom, 2) if denom else None

        # Alerts
        cur = conn.execute(
            "SELECT COUNT(*) as cnt, severity FROM alerts "
            "WHERE opened_at >= ? AND opened_at <= ? GROUP BY severity",
            (start, end),
        )
        alert_counts = {r["severity"]: r["cnt"] for r in cur.fetchall()}
        total_alerts = sum(alert_counts.values())

    finally:
        conn.close()

    return AnalyticsReport(
        from_ts=start,
        to_ts=end,
        from_utc=_utc(start),
        to_utc=_utc(end),
        window_seconds=window_span,
        window_human=_human_span(window_span),
        download_mbps=_aggregate(dl_vals),
        upload_mbps=_aggregate(ul_vals),
        cpu_percent=_aggregate(cpu_vals),
        memory_percent=_aggregate(mem_vals),
        latency_avg_ms=_aggregate(lat_vals),
        packet_loss_percent=_aggregate(loss_vals),
        pps=_aggregate(pps_vals),
        total_packets=total_p,
        tcp_share_pct=_pct(tcp_p, total_p),
        udp_share_pct=_pct(udp_p, total_p),
        icmp_share_pct=_pct(icmp_p, total_p),
        dns_share_pct=_pct(dns_p, total_p),
        ipv4_share_pct=_pct(ipv4_p, total_p),
        ipv6_share_pct=_pct(ipv6_p, total_p),
        total_alerts=total_alerts,
        critical_alerts=alert_counts.get("CRITICAL", 0),
        warning_alerts=alert_counts.get("WARNING", 0),
        info_alerts=alert_counts.get("INFO", 0),
    )


# ─── Singleton ───────────────────────────────────────────────────────────────
analytics_service = type("_AnalyticsService", (), {
    "get_coverage": staticmethod(get_coverage),
    "get_timeseries": staticmethod(get_timeseries),
    "get_report": staticmethod(get_report),
})()
