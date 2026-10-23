# -*- coding: utf-8 -*-
"""Protocol Analytics Service (Phase 11).

Maintains current aggregated window state in memory.
Persists finalized time windows into SQLite (protocol_metrics table).
Supports querying current protocol metrics and paginated history.
Provides lightweight summaries for WebSocket broadcast.
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional
from datetime import datetime, timezone

from backend.collectors.packets import WindowAggregate, packet_collector
from backend.database.models import ProtocolMetricModel
from backend.database.session import SessionLocal
from backend.schemas.protocol import (
    ProtocolHistoryResponse,
    ProtocolSummary,
    ProtocolWindowMetric,
)

logger = logging.getLogger("netwatch.services.protocols")


class ProtocolAnalyticsService:
    """Service managing protocol analytics and time-window persistence."""

    def __init__(self, register_with_collector: bool = True):
        self._lock = threading.RLock()
        self._latest_window: Optional[ProtocolWindowMetric] = None
        self._summary: ProtocolSummary = ProtocolSummary(status="WARMING_UP")

        if register_with_collector:
            packet_collector.register_callback(self.on_window_finalized)

    def on_window_finalized(self, win: WindowAggregate) -> None:
        """Callback invoked when a packet collection time-window completes.
        1. Updates in-memory latest window and lightweight summary.
        2. Persists window summary to SQLite (only if status is LIVE or PERMISSION_REQUIRED transitions).
        """
        metric = ProtocolWindowMetric(
            window_id=win.window_id,
            timestamp=win.timestamp,
            timestamp_utc=win.timestamp_utc,
            interface=win.interface,
            status=win.status,
            window_duration_seconds=win.duration_seconds,
            total_packets=win.total_packets,
            total_bytes=win.total_bytes,
            packets_per_second=win.packets_per_second,
            bytes_per_second=win.bytes_per_second,
            avg_packet_size=win.avg_packet_size,
            tcp_packets=win.tcp_packets,
            udp_packets=win.udp_packets,
            icmp_packets=win.icmp_packets,
            other_transport_packets=win.other_transport_packets,
            dns_packets=win.dns_packets,
            ipv4_packets=win.ipv4_packets,
            ipv6_packets=win.ipv6_packets,
            other_network_packets=win.other_network_packets,
            non_ip_packets=win.non_ip_packets,
            error_message=win.error_message,
        )

        with self._lock:
            self._latest_window = metric
            self._summary = ProtocolSummary(
                status=win.status,
                interface=win.interface,
                pps=win.packets_per_second,
                bps=win.bytes_per_second,
                total_packets=win.total_packets,
                tcp=win.tcp_packets,
                udp=win.udp_packets,
                icmp=win.icmp_packets,
                dns=win.dns_packets,
                other=win.other_transport_packets,
                non_ip=win.non_ip_packets,
                ipv4=win.ipv4_packets,
                ipv6=win.ipv6_packets,
                avg_packet_size=win.avg_packet_size,
                last_window_utc=win.timestamp_utc,
                limitation_reason=win.error_message,
            )

        # Persist to SQLite outside of the packet capture thread
        self._persist_window(metric)

    def _persist_window(self, metric: ProtocolWindowMetric) -> None:
        """Safely saves window summary to database."""
        db = SessionLocal()
        try:
            row = ProtocolMetricModel(
                window_id=metric.window_id,
                timestamp=metric.timestamp,
                timestamp_utc=metric.timestamp_utc,
                interface=metric.interface,
                status=metric.status,
                window_duration_seconds=metric.window_duration_seconds,
                total_packets=metric.total_packets,
                total_bytes=metric.total_bytes,
                packets_per_second=metric.packets_per_second,
                bytes_per_second=metric.bytes_per_second,
                avg_packet_size=metric.avg_packet_size,
                tcp_packets=metric.tcp_packets,
                udp_packets=metric.udp_packets,
                icmp_packets=metric.icmp_packets,
                other_transport_packets=metric.other_transport_packets,
                dns_packets=metric.dns_packets,
                ipv4_packets=metric.ipv4_packets,
                ipv6_packets=metric.ipv6_packets,
                other_network_packets=metric.other_network_packets,
                non_ip_packets=metric.non_ip_packets,
                error_message=metric.error_message,
            )
            db.add(row)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist protocol window metric: {e}")
        finally:
            db.close()

    def get_current(self) -> ProtocolWindowMetric:
        """Returns the most recent aggregated window metric."""
        with self._lock:
            if self._latest_window:
                return self._latest_window

        now = 0.0
        iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ProtocolWindowMetric(
            window_id="init",
            timestamp=now,
            timestamp_utc=iso,
            interface=packet_collector.current_interface,
            status=packet_collector.status,
            error_message=packet_collector.limitation_reason,
        )

    def get_summary(self) -> ProtocolSummary:
        """Returns lightweight protocol summary for WebSocket/KPI."""
        with self._lock:
            return self._summary

    def get_history(
        self,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
        limit: int = 100,
    ) -> ProtocolHistoryResponse:
        """Returns historical aggregated protocol windows from SQLite."""
        db = SessionLocal()
        try:
            q = db.query(ProtocolMetricModel)
            if from_ts is not None:
                q = q.filter(ProtocolMetricModel.timestamp >= from_ts)
            if to_ts is not None:
                q = q.filter(ProtocolMetricModel.timestamp <= to_ts)

            total = q.count()
            rows = q.order_by(ProtocolMetricModel.timestamp.desc()).limit(limit).all()

            items = [ProtocolWindowMetric.model_validate(r) for r in rows]
            return ProtocolHistoryResponse(
                count=len(items),
                total=total,
                items=items,
            )
        finally:
            db.close()


# Global singleton instance
protocol_service = ProtocolAnalyticsService()
