"""Autonomous Telemetry Persistence, Retention, and WebSocket Broadcast Worker (Phase 4 & 5)
Runs independently of frontend requests under a single FastAPI application worker.
"""
import os
import threading
import time
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from backend.core.config import settings
from backend.database.session import SessionLocal, Base, engine
from backend.database.models import (
    SystemMetricModel,
    NetworkMetricModel,
    InterfaceMetricModel,
    LatencyMetricModel,
    ProtocolMetricModel
)
from backend.database.migrations import run_migrations
from backend.collectors.system import system_collector
from backend.collectors.network import network_collector
from backend.collectors.latency import latency_collector
from backend.services.alert_service import alert_service
from backend.services.health_score_service import health_score_service
from backend.services.broadcaster import broadcaster

logger = logging.getLogger("netwatch.storage_worker")

class TelemetryStorageWorker:
    """Background engine that continuously samples and persists telemetry into SQLite.
    Single-worker model: Designed strictly to run within a single application process.
    Also broadcasts each fresh telemetry snapshot to WebSocket clients via broadcaster.
    """

    def __init__(self, interval: float = settings.SAMPLING_INTERVAL_SECONDS):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread = None
        self._last_cleanup_mono: float = time.monotonic()
        self._is_running = False

    def start(self):
        """Initializes database schema, executes migrations, runs startup retention cleanup, and starts background thread."""
        if self._is_running:
            logger.warning("TelemetryStorageWorker start called but worker is already active.")
            return

        Base.metadata.create_all(bind=engine)
        # Apply restrictive permissions (0600) on POSIX
        if os.name != "nt":
            db_path = settings.SQLITE_URL.replace("sqlite:///", "")
            if os.path.exists(db_path):
                try:
                    os.chmod(db_path, 0o600)
                except OSError:
                    pass
        try:
            run_migrations()
        except Exception as e:
            logger.error(f"Migration error during TelemetryStorageWorker start: {e}", exc_info=True)

        # Run retention cleanup on startup so short runs / restarts enforce retention
        try:
            self._run_retention_cleanup()
        except Exception as e:
            logger.error(f"[TelemetryStorageWorker] Initial retention cleanup failed: {e}", exc_info=True)
        self._last_cleanup_mono = time.monotonic()

        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="TelemetryStorageWorker")
        self._thread.start()
        logger.info("TelemetryStorageWorker started successfully.")

    def stop(self, timeout: float = 3.0):
        """Cleanly stops background storage thread on application shutdown."""
        self._stop_event.set()
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("TelemetryStorageWorker stopped cleanly.")

    def _run_loop(self):
        while not self._stop_event.is_set():
            start_time = time.monotonic()
            try:
                self._persist_and_broadcast_tick()
            except Exception as e:
                logger.error(f"[TelemetryStorageWorker] Error in tick: {e}", exc_info=True)

            # Run periodic 7-day retention cleanup
            if time.monotonic() - self._last_cleanup_mono >= settings.CLEANUP_INTERVAL_SECONDS:
                try:
                    self._run_retention_cleanup()
                except Exception as e:
                    logger.error(f"[TelemetryStorageWorker] Error in periodic retention cleanup: {e}", exc_info=True)
                self._last_cleanup_mono = time.monotonic()

            elapsed = time.monotonic() - start_time
            sleep_time = max(0.1, self.interval - elapsed)
            self._stop_event.wait(timeout=sleep_time)

    def _persist_and_broadcast_tick(self):
        """Samples system and network collectors, persists to SQLite, and broadcasts via WebSockets."""
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sample_id = str(uuid.uuid4())

        # Collect current snapshots from existing collectors
        sys_snap = system_collector.collect()
        net_snap = network_collector.collect()
        lat_snap = latency_collector.collect()

        # 1. Open fresh session for this SQLite transaction
        db = SessionLocal()
        try:
            # System Metrics
            sys_row = SystemMetricModel(
                sample_id=sample_id,
                timestamp=now_ts,
                timestamp_utc=now_iso,
                cpu_percent=sys_snap.cpu.usage_percent if sys_snap.cpu.is_ready else None,
                memory_percent=sys_snap.memory.usage_percent,
                memory_used_bytes=sys_snap.memory.used_bytes,
                memory_total_bytes=sys_snap.memory.total_bytes,
                memory_available_bytes=sys_snap.memory.available_bytes,
                disk_percent=sys_snap.disk.usage_percent,
                disk_used_bytes=sys_snap.disk.used_bytes,
                disk_total_bytes=sys_snap.disk.total_bytes,
                disk_free_bytes=sys_snap.disk.free_bytes,
                disk_mount_point=sys_snap.disk.mount_point,
                uptime_seconds=sys_snap.system_uptime_seconds,
                collector_status=sys_snap.collector_status,
                unavailable_fields=json.dumps(sys_snap.unavailable_fields) if sys_snap.unavailable_fields else None
            )
            db.add(sys_row)

            # Network Metrics
            net_row = NetworkMetricModel(
                sample_id=sample_id,
                timestamp=now_ts,
                timestamp_utc=now_iso,
                status=net_snap.status,
                download_mbps=net_snap.download_mbps,
                upload_mbps=net_snap.upload_mbps,
                bytes_recv=net_snap.bytes_recv_total,
                bytes_sent=net_snap.bytes_sent_total,
                packets_recv=net_snap.packets_recv_total,
                packets_sent=net_snap.packets_sent_total,
                elapsed_seconds=net_snap.sample_interval_seconds
            )
            db.add(net_row)

            # Interface Metrics (persist relevant active or traffic-carrying adapters)
            for iface in net_snap.interfaces:
                has_traffic = (iface.bytes_recv > 0 or iface.bytes_sent > 0 or iface.is_up)
                if has_traffic:
                    iface_row = InterfaceMetricModel(
                        sample_id=sample_id,
                        timestamp=now_ts,
                        timestamp_utc=now_iso,
                        interface_name=iface.name,
                        is_up=iface.is_up,
                        download_mbps=iface.download_mbps,
                        upload_mbps=iface.upload_mbps,
                        bytes_recv=iface.bytes_recv,
                        bytes_sent=iface.bytes_sent,
                        packets_recv=iface.packets_recv,
                        packets_sent=iface.packets_sent
                    )
                    db.add(iface_row)

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # 2. Evaluate deterministic alerts and compute network health score
        alert_summary = alert_service.evaluate_tick(sys_snap, net_snap, lat_snap)
        health_score = health_score_service.calculate_score(sys_snap, net_snap, lat_snap, alert_summary)

        # 3. Fetch lightweight device summary (cheap counter query, not a full table scan)
        try:
            from backend.services.device_service import device_service as _dev_svc
            device_summary = _dev_svc.get_device_summary().model_dump()
        except Exception:
            device_summary = None

        # 4. Fetch lightweight connection summary (Phase 10)
        try:
            from backend.services.connection_service import connection_service as _conn_svc
            conn_summary = _conn_svc.get_summary().model_dump()
        except Exception:
            conn_summary = None

        # 5. Fetch lightweight protocol analytics summary (Phase 11)
        try:
            from backend.services.protocol_service import protocol_service as _proto_svc
            proto_summary = _proto_svc.get_summary().model_dump()
        except Exception:
            proto_summary = None

        # 6. Broadcast unified snapshot to all WebSocket clients
        ws_payload = {
            "type": "telemetry",
            "sample_id": sample_id,
            "timestamp_utc": now_iso,
            "system": sys_snap.model_dump(),
            "network": net_snap.model_dump(),
            "latency": lat_snap.model_dump(),
            "health_score": health_score.model_dump(),
            "alerts_summary": alert_summary.model_dump(),
            "devices": device_summary,
            "connections": conn_summary,
            "protocols": proto_summary,
        }
        broadcaster.broadcast_sync(ws_payload)

    def _run_retention_cleanup(self):
        """Purges telemetry older than TELEMETRY_RETENTION_DAYS for all time-series tables.
        Keeps alerts and devices separate (lifecycle/stateful entities).
        """
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=settings.TELEMETRY_RETENTION_DAYS)).timestamp()
        db = SessionLocal()
        try:
            db.query(SystemMetricModel).filter(SystemMetricModel.timestamp < cutoff_ts).delete()
            db.query(NetworkMetricModel).filter(NetworkMetricModel.timestamp < cutoff_ts).delete()
            db.query(InterfaceMetricModel).filter(InterfaceMetricModel.timestamp < cutoff_ts).delete()
            db.query(LatencyMetricModel).filter(LatencyMetricModel.timestamp < cutoff_ts).delete()
            db.query(ProtocolMetricModel).filter(ProtocolMetricModel.timestamp < cutoff_ts).delete()
            db.commit()
            logger.info(f"[TelemetryStorageWorker] Retention cleanup completed successfully (cutoff_ts={cutoff_ts}).")
        except Exception as e:
            db.rollback()
            logger.error(f"[TelemetryStorageWorker] Error in retention cleanup transaction: {e}", exc_info=True)
            raise
        finally:
            db.close()

# Global storage worker instance
storage_worker = TelemetryStorageWorker()
