"""Deterministic Network Health Scoring Engine (Phase 8)
Calculates a transparent 0-100 health score directly from live telemetry snapshots
with an itemized deduction ledger and explicit handling for unavailable/stale data.
"""
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.core.config import settings
from backend.schemas.health_score import HealthScoreResponse, ScoreDeduction
from backend.schemas.system import SystemTelemetryResponse
from backend.schemas.network import NetworkThroughputResponse
from backend.schemas.latency import LatencySnapshot
from backend.schemas.alert import AlertSummary

class HealthScoreService:
    """Calculates network and host health score with transparent, non-overlapping deductions."""

    @staticmethod
    def get_health_label(score: int) -> str:
        """Standardized NetWatch health classification labels."""
        if score >= 90:
            return "HEALTHY"
        elif score >= 70:
            return "DEGRADED"
        elif score >= 40:
            return "POOR"
        else:
            return "CRITICAL"

    def calculate_score(
        self,
        sys_snap: SystemTelemetryResponse,
        net_snap: NetworkThroughputResponse,
        lat_snap: LatencySnapshot,
        alert_summary: Optional[AlertSummary] = None
    ) -> HealthScoreResponse:
        """Derives a transparent 0-100 health score from live telemetry.
        Never treats unavailable/warming-up telemetry as healthy or as zero.
        """
        deductions: List[ScoreDeduction] = []

        # -------------------------------------------------------------
        # 1. Connectivity & Latency Target Health
        # -------------------------------------------------------------
        if lat_snap.status == "UNREACHABLE" or (not lat_snap.is_reachable and lat_snap.status != "WARMING_UP"):
            deductions.append(ScoreDeduction(
                category="Connectivity",
                reason=f"Target {lat_snap.target} is unreachable",
                points=35,
                observed_value="100% loss"
            ))
        elif lat_snap.status == "WARMING_UP":
            deductions.append(ScoreDeduction(
                category="Connectivity",
                reason="Latency monitoring baseline is warming up",
                points=5,
                observed_value="WARMING_UP"
            ))
        else:
            # Target is reachable - evaluate packet loss and latency without double penalty
            loss = lat_snap.packet_loss_percent
            if loss is not None and loss > 0:
                if loss >= settings.ALERT_PACKET_LOSS_CRITICAL:
                    deductions.append(ScoreDeduction(
                        category="Packet Loss",
                        reason=f"High packet loss to {lat_snap.target}",
                        points=20,
                        observed_value=f"{loss:.1f}%"
                    ))
                elif loss >= settings.ALERT_PACKET_LOSS_WARNING:
                    deductions.append(ScoreDeduction(
                        category="Packet Loss",
                        reason=f"Moderate packet loss to {lat_snap.target}",
                        points=10,
                        observed_value=f"{loss:.1f}%"
                    ))

            lat = lat_snap.latency_avg_ms or lat_snap.latency_last_ms
            if lat is not None:
                if lat >= settings.ALERT_LATENCY_CRITICAL_MS:
                    deductions.append(ScoreDeduction(
                        category="Latency",
                        reason=f"Critical network latency to {lat_snap.target}",
                        points=15,
                        observed_value=f"{lat:.1f} ms"
                    ))
                elif lat >= settings.ALERT_LATENCY_WARNING_MS:
                    deductions.append(ScoreDeduction(
                        category="Latency",
                        reason=f"Elevated network latency to {lat_snap.target}",
                        points=8,
                        observed_value=f"{lat:.1f} ms"
                    ))

        # Check for latency staleness
        if lat_snap.is_stale:
            deductions.append(ScoreDeduction(
                category="Freshness",
                reason=f"Latency probe data is stale (age: {lat_snap.probe_age_seconds}s)",
                points=8,
                observed_value=f"{lat_snap.probe_age_seconds}s"
            ))

        # -------------------------------------------------------------
        # 2. Network Collector Throughput State
        # -------------------------------------------------------------
        if net_snap.status == "WARMING_UP":
            deductions.append(ScoreDeduction(
                category="Network Collector",
                reason="Network throughput delta baseline warming up",
                points=5,
                observed_value="WARMING_UP"
            ))
        elif net_snap.status == "RESET":
            deductions.append(ScoreDeduction(
                category="Network Collector",
                reason="Network adapter counter reset or reconnected",
                points=10,
                observed_value="RESET"
            ))

        # -------------------------------------------------------------
        # 3. Host System Resource Health
        # -------------------------------------------------------------
        # CPU
        if not sys_snap.cpu.is_ready or sys_snap.cpu.usage_percent is None:
            deductions.append(ScoreDeduction(
                category="Host Resources",
                reason="CPU telemetry initializing / unavailable",
                points=5,
                observed_value="UNAVAILABLE"
            ))
        else:
            cpu = sys_snap.cpu.usage_percent
            if cpu >= settings.ALERT_CPU_CRITICAL:
                deductions.append(ScoreDeduction(
                    category="Host Resources",
                    reason="Host CPU usage critical",
                    points=15,
                    observed_value=f"{cpu:.1f}%"
                ))
            elif cpu >= settings.ALERT_CPU_WARNING:
                deductions.append(ScoreDeduction(
                    category="Host Resources",
                    reason="Host CPU usage elevated",
                    points=7,
                    observed_value=f"{cpu:.1f}%"
                ))

        # Memory
        mem = sys_snap.memory.usage_percent
        if mem is not None:
            if mem >= settings.ALERT_MEMORY_CRITICAL:
                deductions.append(ScoreDeduction(
                    category="Host Resources",
                    reason="Host memory usage critical",
                    points=15,
                    observed_value=f"{mem:.1f}%"
                ))
            elif mem >= settings.ALERT_MEMORY_WARNING:
                deductions.append(ScoreDeduction(
                    category="Host Resources",
                    reason="Host memory usage elevated",
                    points=7,
                    observed_value=f"{mem:.1f}%"
                ))

        # Storage Disk
        disk = sys_snap.disk.usage_percent
        if disk is not None:
            if disk >= settings.ALERT_DISK_CRITICAL:
                deductions.append(ScoreDeduction(
                    category="Host Resources",
                    reason="Host volume utilization critical",
                    points=15,
                    observed_value=f"{disk:.1f}%"
                ))
            elif disk >= settings.ALERT_DISK_WARNING:
                deductions.append(ScoreDeduction(
                    category="Host Resources",
                    reason="Host volume utilization elevated",
                    points=7,
                    observed_value=f"{disk:.1f}%"
                ))

        # System collector status
        if sys_snap.collector_status != "OK":
            deductions.append(ScoreDeduction(
                category="Collector Health",
                reason=f"System collector degraded ({sys_snap.collector_status})",
                points=10,
                observed_value=sys_snap.collector_status
            ))

        # -------------------------------------------------------------
        # 4. Score Calculation & Clamping (0-100)
        # -------------------------------------------------------------
        total_deductions = sum(d.points for d in deductions)
        score = max(0, min(100, 100 - total_deductions))
        status = self.get_health_label(score)

        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        freshness_info = {
            "system_status": sys_snap.collector_status,
            "network_status": net_snap.status,
            "latency_status": lat_snap.status,
            "latency_age_seconds": lat_snap.probe_age_seconds,
            "is_latency_stale": lat_snap.is_stale,
            "sample_interval_seconds": net_snap.sample_interval_seconds
        }

        return HealthScoreResponse(
            score=score,
            status=status,
            timestamp=now_ts,
            timestamp_utc=now_iso,
            deductions=deductions,
            telemetry_freshness=freshness_info
        )

health_score_service = HealthScoreService()
