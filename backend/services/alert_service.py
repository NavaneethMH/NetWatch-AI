"""Deterministic Alert Engine (Phase 8)
Evaluates real telemetry snapshots against configured thresholds with consecutive-sample protection,
deduplication, and persistent lifecycle management (OPEN, ACKNOWLEDGED, RESOLVED).
"""
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, List
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database.session import SessionLocal
from backend.database.alert_repository import alert_repo
from backend.schemas.alert import AlertSummary
from backend.schemas.system import SystemTelemetryResponse
from backend.schemas.network import NetworkThroughputResponse
from backend.schemas.latency import LatencySnapshot

logger = logging.getLogger("netwatch.services.alert")

class AlertConditionCheck:
    def __init__(
        self,
        alert_type: str,
        source: str,
        is_violated: bool,
        severity: str,
        message: str,
        metric_name: str,
        observed_value: Optional[float],
        threshold_value: Optional[float]
    ):
        self.alert_type = alert_type
        self.source = source
        self.is_violated = is_violated
        self.severity = severity
        self.message = message
        self.metric_name = metric_name
        self.observed_value = observed_value
        self.threshold_value = threshold_value

class AlertService:
    def __init__(self):
        # In-memory consecutive counters: (type, source) -> count
        self._violation_counts: Dict[Tuple[str, str], int] = {}
        self._clear_counts: Dict[Tuple[str, str], int] = {}
        self._last_summary = AlertSummary(
            total_active=0,
            open_count=0,
            acknowledged_count=0,
            critical_count=0,
            warning_count=0,
            info_count=0
        )

    def evaluate_tick(
        self,
        sys_snap: SystemTelemetryResponse,
        net_snap: NetworkThroughputResponse,
        lat_snap: LatencySnapshot
    ) -> AlertSummary:
        """Evaluates live telemetry snapshots against all deterministic alert rules.
        Executed by the storage worker outside collector threads.
        """
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        checks: List[AlertConditionCheck] = []

        # 1. System Host Metrics (CPU, Memory, Disk)
        # Never treat null or not ready as 0.0
        if sys_snap.cpu.is_ready and sys_snap.cpu.usage_percent is not None:
            cpu_val = sys_snap.cpu.usage_percent
            if cpu_val >= settings.ALERT_CPU_CRITICAL:
                checks.append(AlertConditionCheck(
                    alert_type="CPU_HIGH",
                    source="host",
                    is_violated=True,
                    severity="CRITICAL",
                    message=f"Host CPU utilization is critical at {cpu_val:.1f}% (threshold: {settings.ALERT_CPU_CRITICAL}%)",
                    metric_name="cpu_percent",
                    observed_value=cpu_val,
                    threshold_value=settings.ALERT_CPU_CRITICAL
                ))
            elif cpu_val >= settings.ALERT_CPU_WARNING:
                checks.append(AlertConditionCheck(
                    alert_type="CPU_HIGH",
                    source="host",
                    is_violated=True,
                    severity="WARNING",
                    message=f"Host CPU utilization is elevated at {cpu_val:.1f}% (threshold: {settings.ALERT_CPU_WARNING}%)",
                    metric_name="cpu_percent",
                    observed_value=cpu_val,
                    threshold_value=settings.ALERT_CPU_WARNING
                ))
            else:
                checks.append(AlertConditionCheck(
                    alert_type="CPU_HIGH",
                    source="host",
                    is_violated=False,
                    severity="INFO",
                    message="Host CPU utilization within normal limits",
                    metric_name="cpu_percent",
                    observed_value=cpu_val,
                    threshold_value=settings.ALERT_CPU_WARNING
                ))

        if sys_snap.memory.usage_percent is not None:
            mem_val = sys_snap.memory.usage_percent
            if mem_val >= settings.ALERT_MEMORY_CRITICAL:
                checks.append(AlertConditionCheck(
                    alert_type="MEMORY_HIGH",
                    source="host",
                    is_violated=True,
                    severity="CRITICAL",
                    message=f"Host memory utilization is critical at {mem_val:.1f}% (threshold: {settings.ALERT_MEMORY_CRITICAL}%)",
                    metric_name="memory_percent",
                    observed_value=mem_val,
                    threshold_value=settings.ALERT_MEMORY_CRITICAL
                ))
            elif mem_val >= settings.ALERT_MEMORY_WARNING:
                checks.append(AlertConditionCheck(
                    alert_type="MEMORY_HIGH",
                    source="host",
                    is_violated=True,
                    severity="WARNING",
                    message=f"Host memory utilization is elevated at {mem_val:.1f}% (threshold: {settings.ALERT_MEMORY_WARNING}%)",
                    metric_name="memory_percent",
                    observed_value=mem_val,
                    threshold_value=settings.ALERT_MEMORY_WARNING
                ))
            else:
                checks.append(AlertConditionCheck(
                    alert_type="MEMORY_HIGH",
                    source="host",
                    is_violated=False,
                    severity="INFO",
                    message="Host memory utilization within normal limits",
                    metric_name="memory_percent",
                    observed_value=mem_val,
                    threshold_value=settings.ALERT_MEMORY_WARNING
                ))

        if sys_snap.disk.usage_percent is not None:
            disk_val = sys_snap.disk.usage_percent
            if disk_val >= settings.ALERT_DISK_CRITICAL:
                checks.append(AlertConditionCheck(
                    alert_type="DISK_HIGH",
                    source="host",
                    is_violated=True,
                    severity="CRITICAL",
                    message=f"Host storage volume utilization is critical at {disk_val:.1f}% (threshold: {settings.ALERT_DISK_CRITICAL}%)",
                    metric_name="disk_percent",
                    observed_value=disk_val,
                    threshold_value=settings.ALERT_DISK_CRITICAL
                ))
            elif disk_val >= settings.ALERT_DISK_WARNING:
                checks.append(AlertConditionCheck(
                    alert_type="DISK_HIGH",
                    source="host",
                    is_violated=True,
                    severity="WARNING",
                    message=f"Host storage volume utilization is elevated at {disk_val:.1f}% (threshold: {settings.ALERT_DISK_WARNING}%)",
                    metric_name="disk_percent",
                    observed_value=disk_val,
                    threshold_value=settings.ALERT_DISK_WARNING
                ))
            else:
                checks.append(AlertConditionCheck(
                    alert_type="DISK_HIGH",
                    source="host",
                    is_violated=False,
                    severity="INFO",
                    message="Host storage volume utilization within normal limits",
                    metric_name="disk_percent",
                    observed_value=disk_val,
                    threshold_value=settings.ALERT_DISK_WARNING
                ))

        # 2. System Collector Status
        if sys_snap.collector_status != "OK":
            checks.append(AlertConditionCheck(
                alert_type="SYSTEM_COLLECTOR_DEGRADED",
                source="system_collector",
                is_violated=True,
                severity="WARNING",
                message=f"System telemetry collector is reporting degraded status: {sys_snap.collector_status}",
                metric_name="collector_status",
                observed_value=None,
                threshold_value=None
            ))
        else:
            checks.append(AlertConditionCheck(
                alert_type="SYSTEM_COLLECTOR_DEGRADED",
                source="system_collector",
                is_violated=False,
                severity="INFO",
                message="System collector operating normally",
                metric_name="collector_status",
                observed_value=None,
                threshold_value=None
            ))

        # 3. Network Collector Status
        if net_snap.status in ("RESET", "WARMING_UP"):
            checks.append(AlertConditionCheck(
                alert_type="NETWORK_COLLECTOR_DEGRADED",
                source="network_collector",
                is_violated=True,
                severity="WARNING",
                message=f"Network throughput collector is in {net_snap.status} state",
                metric_name="network_status",
                observed_value=None,
                threshold_value=None
            ))
        else:
            checks.append(AlertConditionCheck(
                alert_type="NETWORK_COLLECTOR_DEGRADED",
                source="network_collector",
                is_violated=False,
                severity="INFO",
                message="Network throughput collector operating normally",
                metric_name="network_status",
                observed_value=None,
                threshold_value=None
            ))

        # 4. Latency Target Unreachable
        target_name = lat_snap.target or settings.PING_TARGET
        if lat_snap.status == "UNREACHABLE" or (not lat_snap.is_reachable and lat_snap.status != "WARMING_UP"):
            checks.append(AlertConditionCheck(
                alert_type="TARGET_UNREACHABLE",
                source=target_name,
                is_violated=True,
                severity="CRITICAL",
                message=f"Latency probe target {target_name} is unreachable (100% packet loss)",
                metric_name="is_reachable",
                observed_value=0.0,
                threshold_value=1.0
            ))
        else:
            checks.append(AlertConditionCheck(
                alert_type="TARGET_UNREACHABLE",
                source=target_name,
                is_violated=False,
                severity="INFO",
                message=f"Target {target_name} reachable",
                metric_name="is_reachable",
                observed_value=1.0 if lat_snap.is_reachable else None,
                threshold_value=1.0
            ))

        # 5. High Latency (Only if reachable and latency is available)
        lat_val = lat_snap.latency_avg_ms or lat_snap.latency_last_ms
        if lat_snap.is_reachable and lat_val is not None:
            if lat_val >= settings.ALERT_LATENCY_CRITICAL_MS:
                checks.append(AlertConditionCheck(
                    alert_type="LATENCY_HIGH",
                    source=target_name,
                    is_violated=True,
                    severity="CRITICAL",
                    message=f"Network latency to {target_name} is critical at {lat_val:.1f} ms (threshold: {settings.ALERT_LATENCY_CRITICAL_MS} ms)",
                    metric_name="latency_ms",
                    observed_value=lat_val,
                    threshold_value=settings.ALERT_LATENCY_CRITICAL_MS
                ))
            elif lat_val >= settings.ALERT_LATENCY_WARNING_MS:
                checks.append(AlertConditionCheck(
                    alert_type="LATENCY_HIGH",
                    source=target_name,
                    is_violated=True,
                    severity="WARNING",
                    message=f"Network latency to {target_name} is elevated at {lat_val:.1f} ms (threshold: {settings.ALERT_LATENCY_WARNING_MS} ms)",
                    metric_name="latency_ms",
                    observed_value=lat_val,
                    threshold_value=settings.ALERT_LATENCY_WARNING_MS
                ))
            else:
                checks.append(AlertConditionCheck(
                    alert_type="LATENCY_HIGH",
                    source=target_name,
                    is_violated=False,
                    severity="INFO",
                    message=f"Latency to {target_name} is normal",
                    metric_name="latency_ms",
                    observed_value=lat_val,
                    threshold_value=settings.ALERT_LATENCY_WARNING_MS
                ))

        # 6. Packet Loss (When target is tested and not 100% unreachable already reported)
        loss_val = lat_snap.packet_loss_percent
        if loss_val is not None and lat_snap.status in ("LIVE", "PARTIAL"):
            if loss_val >= settings.ALERT_PACKET_LOSS_CRITICAL:
                checks.append(AlertConditionCheck(
                    alert_type="PACKET_LOSS_HIGH",
                    source=target_name,
                    is_violated=True,
                    severity="CRITICAL",
                    message=f"Packet loss to {target_name} is critical at {loss_val:.1f}% (threshold: {settings.ALERT_PACKET_LOSS_CRITICAL}%)",
                    metric_name="packet_loss_percent",
                    observed_value=loss_val,
                    threshold_value=settings.ALERT_PACKET_LOSS_CRITICAL
                ))
            elif loss_val >= settings.ALERT_PACKET_LOSS_WARNING:
                checks.append(AlertConditionCheck(
                    alert_type="PACKET_LOSS_HIGH",
                    source=target_name,
                    is_violated=True,
                    severity="WARNING",
                    message=f"Packet loss to {target_name} is elevated at {loss_val:.1f}% (threshold: {settings.ALERT_PACKET_LOSS_WARNING}%)",
                    metric_name="packet_loss_percent",
                    observed_value=loss_val,
                    threshold_value=settings.ALERT_PACKET_LOSS_WARNING
                ))
            else:
                checks.append(AlertConditionCheck(
                    alert_type="PACKET_LOSS_HIGH",
                    source=target_name,
                    is_violated=False,
                    severity="INFO",
                    message=f"Packet loss to {target_name} is normal",
                    metric_name="packet_loss_percent",
                    observed_value=loss_val,
                    threshold_value=settings.ALERT_PACKET_LOSS_WARNING
                ))

        # 7. Stale Latency Telemetry
        if lat_snap.is_stale:
            checks.append(AlertConditionCheck(
                alert_type="LATENCY_STALE",
                source=target_name,
                is_violated=True,
                severity="WARNING",
                message=f"Latency probe data for {target_name} is stale (age: {lat_snap.probe_age_seconds}s)",
                metric_name="is_stale",
                observed_value=lat_snap.probe_age_seconds,
                threshold_value=settings.PING_INTERVAL_SECONDS * 2.5
            ))
        else:
            checks.append(AlertConditionCheck(
                alert_type="LATENCY_STALE",
                source=target_name,
                is_violated=False,
                severity="INFO",
                message=f"Latency data for {target_name} is fresh",
                metric_name="is_stale",
                observed_value=lat_snap.probe_age_seconds,
                threshold_value=settings.PING_INTERVAL_SECONDS * 2.5
            ))

        # Process all checks against database and consecutive-sample counters
        db = SessionLocal()
        try:
            for check in checks:
                self._process_condition(db, check, now_ts, now_iso)
            summary = alert_repo.get_active_summary(db)
            self._last_summary = summary
            return summary
        except Exception as e:
            logger.error(f"Error evaluating alerts: {e}", exc_info=True)
            db.rollback()
            return self._last_summary
        finally:
            db.close()

    def _process_condition(
        self,
        db: Session,
        check: AlertConditionCheck,
        now_ts: float,
        now_iso: str
    ):
        """Applies consecutive-sample filtering, deduplication, and resolution."""
        key = (check.alert_type, check.source)
        existing_alert = alert_repo.get_active_alert(db, check.alert_type, check.source)

        if check.is_violated:
            # Condition is currently violating
            self._clear_counts[key] = 0
            v_count = self._violation_counts.get(key, 0) + 1
            self._violation_counts[key] = v_count

            # Immediate threshold for connectivity/collector failures, or consecutive samples for spikes
            # Note: TARGET_UNREACHABLE probe already runs Ping count (e.g. 4 pings); 2 consecutive ticks is enough
            required_violations = 1 if check.alert_type in ("TARGET_UNREACHABLE", "LATENCY_STALE") else settings.ALERT_CONSECUTIVE_SAMPLES

            if v_count >= required_violations:
                if existing_alert:
                    # Deduplication: update existing active alert (OPEN or ACKNOWLEDGED)
                    alert_repo.update_active_alert(
                        db=db,
                        alert=existing_alert,
                        observed_value=check.observed_value,
                        severity=check.severity,
                        message=check.message,
                        timestamp=now_ts,
                        timestamp_utc=now_iso
                    )
                else:
                    # Open new alert
                    alert_repo.create_alert(
                        db=db,
                        alert_type=check.alert_type,
                        severity=check.severity,
                        source=check.source,
                        message=check.message,
                        metric_name=check.metric_name,
                        observed_value=check.observed_value,
                        threshold_value=check.threshold_value,
                        timestamp=now_ts,
                        timestamp_utc=now_iso
                    )
                    logger.info(f"Opened new {check.severity} alert: {check.alert_type} on {check.source}")
        else:
            # Condition is normal
            self._violation_counts[key] = 0
            c_count = self._clear_counts.get(key, 0) + 1
            self._clear_counts[key] = c_count

            # Resolve if condition has cleared for required consecutive samples
            if existing_alert and c_count >= settings.ALERT_RESOLVE_CONSECUTIVE_SAMPLES:
                alert_repo.resolve_alert(db, existing_alert, now_ts, now_iso)
                logger.info(f"Resolved alert: {check.alert_type} on {check.source}")

    def get_summary(self, db: Optional[Session] = None) -> AlertSummary:
        """Returns the current active alert summary."""
        if db:
            return alert_repo.get_active_summary(db)
        return self._last_summary

alert_service = AlertService()
