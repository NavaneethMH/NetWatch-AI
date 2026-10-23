"""History Service Layer for System, Network, and Interface Telemetry"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from backend.database.models import (
    SystemMetricModel,
    NetworkMetricModel,
    InterfaceMetricModel
)
from backend.schemas.history import (
    SystemHistoryResponse,
    SystemHistoryItem,
    NetworkHistoryResponse,
    NetworkHistoryItem,
    InterfaceHistoryResponse,
    InterfaceHistoryItem
)

class HistoryService:
    @staticmethod
    def get_system_history(
        db: Session,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 120,
        order: str = "desc"
    ) -> SystemHistoryResponse:
        query = db.query(SystemMetricModel)
        if start_time is not None:
            query = query.filter(SystemMetricModel.timestamp >= start_time)
        if end_time is not None:
            query = query.filter(SystemMetricModel.timestamp <= end_time)

        order_col = desc(SystemMetricModel.timestamp) if order.lower() == "desc" else asc(SystemMetricModel.timestamp)
        rows = query.order_by(order_col).limit(min(1000, max(1, limit))).all()

        items = [
            SystemHistoryItem(
                id=r.id,
                sample_id=r.sample_id,
                timestamp=r.timestamp,
                timestamp_utc=r.timestamp_utc,
                cpu_percent=r.cpu_percent,
                memory_percent=r.memory_percent,
                memory_used_bytes=r.memory_used_bytes,
                memory_total_bytes=r.memory_total_bytes,
                disk_percent=r.disk_percent,
                disk_used_bytes=r.disk_used_bytes,
                disk_total_bytes=r.disk_total_bytes,
                uptime_seconds=r.uptime_seconds,
                collector_status=r.collector_status,
                unavailable_fields=r.unavailable_fields
            )
            for r in rows
        ]
        return SystemHistoryResponse(count=len(items), limit=limit, items=items)

    @staticmethod
    def get_network_history(
        db: Session,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 120,
        order: str = "desc"
    ) -> NetworkHistoryResponse:
        query = db.query(NetworkMetricModel)
        if start_time is not None:
            query = query.filter(NetworkMetricModel.timestamp >= start_time)
        if end_time is not None:
            query = query.filter(NetworkMetricModel.timestamp <= end_time)

        order_col = desc(NetworkMetricModel.timestamp) if order.lower() == "desc" else asc(NetworkMetricModel.timestamp)
        rows = query.order_by(order_col).limit(min(1000, max(1, limit))).all()

        items = [
            NetworkHistoryItem(
                id=r.id,
                sample_id=r.sample_id,
                timestamp=r.timestamp,
                timestamp_utc=r.timestamp_utc,
                status=r.status,
                download_mbps=r.download_mbps,
                upload_mbps=r.upload_mbps,
                bytes_recv=r.bytes_recv,
                bytes_sent=r.bytes_sent,
                packets_recv=r.packets_recv,
                packets_sent=r.packets_sent,
                elapsed_seconds=r.elapsed_seconds
            )
            for r in rows
        ]
        return NetworkHistoryResponse(count=len(items), limit=limit, items=items)

    @staticmethod
    def get_interface_history(
        db: Session,
        interface_name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 120,
        order: str = "desc"
    ) -> InterfaceHistoryResponse:
        query = db.query(InterfaceMetricModel).filter(InterfaceMetricModel.interface_name == interface_name)
        if start_time is not None:
            query = query.filter(InterfaceMetricModel.timestamp >= start_time)
        if end_time is not None:
            query = query.filter(InterfaceMetricModel.timestamp <= end_time)

        order_col = desc(InterfaceMetricModel.timestamp) if order.lower() == "desc" else asc(InterfaceMetricModel.timestamp)
        rows = query.order_by(order_col).limit(min(1000, max(1, limit))).all()

        items = [
            InterfaceHistoryItem(
                id=r.id,
                sample_id=r.sample_id,
                timestamp=r.timestamp,
                timestamp_utc=r.timestamp_utc,
                interface_name=r.interface_name,
                is_up=r.is_up,
                download_mbps=r.download_mbps,
                upload_mbps=r.upload_mbps,
                bytes_recv=r.bytes_recv,
                bytes_sent=r.bytes_sent,
                packets_recv=r.packets_recv,
                packets_sent=r.packets_sent
            )
            for r in rows
        ]
        return InterfaceHistoryResponse(interface_name=interface_name, count=len(items), limit=limit, items=items)

history_service = HistoryService()
