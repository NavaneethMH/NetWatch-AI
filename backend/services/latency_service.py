"""Latency Service Layer for Current and Historical Probes (Phase 7)"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from backend.collectors.latency import latency_collector
from backend.database.models import LatencyMetricModel
from backend.schemas.latency import (
    LatencySnapshot,
    LatencyHistoryResponse,
    LatencyHistoryItem
)

from backend.database.session import SessionLocal
import logging

logger = logging.getLogger("netwatch.services.latency")

class LatencyService:
    @staticmethod
    def get_current_latency() -> LatencySnapshot:
        """Returns the most recent genuine network probe snapshot, with age and staleness."""
        return latency_collector.collect()

    @staticmethod
    def get_latency_history(
        db: Session,
        target: Optional[str] = None,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
        limit: int = 120,
        order: str = "desc"
    ) -> LatencyHistoryResponse:
        """Returns genuine historical latency probe records stored in SQLite."""
        query = db.query(LatencyMetricModel)
        
        if target:
            query = query.filter(LatencyMetricModel.target == target)
        if from_ts is not None:
            query = query.filter(LatencyMetricModel.timestamp >= from_ts)
        if to_ts is not None:
            query = query.filter(LatencyMetricModel.timestamp <= to_ts)

        order_col = desc(LatencyMetricModel.timestamp) if order.lower() == "desc" else asc(LatencyMetricModel.timestamp)
        bounded_limit = min(1000, max(1, limit))
        rows = query.order_by(order_col).limit(bounded_limit).all()

        items = [
            LatencyHistoryItem(
                id=r.id,
                probe_id=r.probe_id,
                timestamp=r.timestamp,
                timestamp_utc=r.timestamp_utc,
                target=r.target,
                status=r.status,
                is_reachable=r.is_reachable,
                packets_sent=r.packets_sent,
                packets_received=r.packets_received,
                packet_loss_percent=r.packet_loss_percent,
                latency_last_ms=r.latency_last_ms,
                latency_min_ms=r.latency_min_ms,
                latency_max_ms=r.latency_max_ms,
                latency_avg_ms=r.latency_avg_ms
            )
            for r in rows
        ]

        return LatencyHistoryResponse(
            target=target,
            count=len(items),
            limit=bounded_limit,
            items=items
        )

    @staticmethod
    def persist_probe(snap: LatencySnapshot):
        """Persists genuine probe result to the latency_metrics table."""
        db = SessionLocal()
        try:
            row = LatencyMetricModel(
                probe_id=snap.probe_id,
                timestamp=snap.timestamp,
                timestamp_utc=snap.timestamp_utc,
                target=snap.target,
                status=snap.status,
                is_reachable=snap.is_reachable,
                packets_sent=snap.packets_sent,
                packets_received=snap.packets_received,
                packet_loss_percent=snap.packet_loss_percent,
                latency_last_ms=snap.latency_last_ms,
                latency_min_ms=snap.latency_min_ms,
                latency_max_ms=snap.latency_max_ms,
                latency_avg_ms=snap.latency_avg_ms
            )
            db.add(row)
            db.commit()
            logger.debug(f"Persisted latency probe {snap.probe_id} for {snap.target} (status={snap.status})")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist latency probe: {e}", exc_info=True)
        finally:
            db.close()

latency_service = LatencyService()
latency_collector.register_callback(latency_service.persist_probe)
