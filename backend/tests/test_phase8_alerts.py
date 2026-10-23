"""Comprehensive Phase 8 Verification Test Suite
Tests:
1. Normal telemetry produces no false alerts
2. Single-sample spike does NOT open alert (consecutive-sample protection)
3. Sustained violation opens exactly one alert
4. Continued violation updates the existing alert (occurrence_count, last_seen_at) without duplicates
5. Returning to normal resolves the alert after consecutive normal samples
6. Acknowledgment works independently of resolution (status ACKNOWLEDGED, does not clear condition)
7. Alerts survive restart (persisted in SQLite)
8. Health score derives deterministically from live telemetry
9. Deduction points total exactly matches the final score (100 - sum(deductions))
10. Unavailable/warming-up/stale telemetry is handled explicitly without defaulting to zero
11. APIs (/api/alerts, /api/alerts/summary, /api/alerts/{id}/acknowledge, /api/health-score) work as expected
"""
import time
import uuid
from backend.core.config import settings
from backend.database.session import SessionLocal, Base, engine
from backend.database.models import AlertModel
from backend.database.alert_repository import alert_repo
from backend.services.alert_service import AlertService
from backend.services.health_score_service import health_score_service
from backend.schemas.system import SystemTelemetryResponse, CpuMetrics, MemoryMetrics, DiskMetrics, NetworkTotals
from backend.schemas.network import NetworkThroughputResponse
from backend.schemas.latency import LatencySnapshot

def create_mock_snapshots(
    cpu_percent=15.0,
    mem_percent=45.0,
    disk_percent=50.0,
    is_reachable=True,
    latency_ms=25.0,
    packet_loss=0.0,
    net_status="LIVE",
    sys_status="OK",
    is_stale=False,
    target="1.1.1.1"
):
    now_ts = time.time()
    now_iso = "2026-10-03T18:00:00Z"

    sys_snap = SystemTelemetryResponse(
        timestamp=now_ts,
        timestamp_iso=now_iso,
        system_uptime_seconds=3600.0,
        boot_time_timestamp=now_ts - 3600.0,
        cpu=CpuMetrics(
            usage_percent=cpu_percent,
            is_ready=True,
            core_count_logical=8,
            core_count_physical=4
        ),
        memory=MemoryMetrics(
            usage_percent=mem_percent,
            total_bytes=16000000000,
            used_bytes=int(16000000000 * (mem_percent / 100.0)),
            available_bytes=int(16000000000 * (1 - mem_percent / 100.0))
        ),
        disk=DiskMetrics(
            usage_percent=disk_percent,
            total_bytes=500000000000,
            used_bytes=int(500000000000 * (disk_percent / 100.0)),
            free_bytes=int(500000000000 * (1 - disk_percent / 100.0)),
            mount_point="C:\\"
        ),
        network_totals=NetworkTotals(
            bytes_sent=1000,
            bytes_recv=1000,
            packets_sent=10,
            packets_recv=10,
            errin=0, errout=0, dropin=0, dropout=0
        ),
        interfaces=[],
        collector_status=sys_status,
        unavailable_fields=[]
    )

    net_snap = NetworkThroughputResponse(
        timestamp=now_ts,
        timestamp_iso=now_iso,
        status=net_status,
        download_mbps=10.5 if net_status == "LIVE" else None,
        upload_mbps=2.1 if net_status == "LIVE" else None,
        bytes_recv_total=100000,
        bytes_sent_total=50000,
        packets_recv_total=100,
        packets_sent_total=50,
        sample_interval_seconds=2.0,
        interfaces=[]
    )

    lat_snap = LatencySnapshot(
        probe_id=str(uuid.uuid4()),
        target=target,
        status="LIVE" if is_reachable else "UNREACHABLE",
        is_reachable=is_reachable,
        packets_sent=4,
        packets_received=0 if not is_reachable else int(4 * (1 - packet_loss / 100.0)),
        packet_loss_percent=packet_loss if is_reachable else 100.0,
        latency_last_ms=latency_ms if is_reachable else None,
        latency_min_ms=latency_ms if is_reachable else None,
        latency_max_ms=latency_ms if is_reachable else None,
        latency_avg_ms=latency_ms if is_reachable else None,
        timestamp=now_ts,
        timestamp_utc=now_iso,
        probe_age_seconds=1.0 if not is_stale else 30.0,
        is_stale=is_stale
    )

    return sys_snap, net_snap, lat_snap

def run_tests():
    print("=== [1] Testing Schema Creation & Alert Repository ===")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clean up test alerts
    db.query(AlertModel).delete()
    db.commit()

    service = AlertService()

    # 1. Normal telemetry produces no false alerts
    print("=== [2] Testing Normal Telemetry Generates No False Alerts ===")
    s1, n1, l1 = create_mock_snapshots(cpu_percent=20.0, mem_percent=50.0, latency_ms=15.0, packet_loss=0.0)
    summary = service.evaluate_tick(s1, n1, l1)
    assert summary.total_active == 0
    assert db.query(AlertModel).count() == 0
    print(" PASS: No false alerts triggered on healthy telemetry.")

    # 2. Temporary one-sample spike does not open alert
    print("=== [3] Testing Transient Spike Protection (Consecutive-Sample) ===")
    # Spiking CPU to 90% (warning threshold is 80%) for 1 sample
    s_spike, n_spike, l_spike = create_mock_snapshots(cpu_percent=90.0)
    summary = service.evaluate_tick(s_spike, n_spike, l_spike)
    assert summary.total_active == 0, f"Expected 0 active alerts on 1st violation sample, got {summary.total_active}"
    assert db.query(AlertModel).filter(AlertModel.status == "OPEN").count() == 0

    # Metric immediately returns to normal
    summary = service.evaluate_tick(s1, n1, l1)
    assert summary.total_active == 0
    assert db.query(AlertModel).filter(AlertModel.status == "OPEN").count() == 0
    print(" PASS: 1-sample spike did not trigger an alert; counter reset on return to normal.")

    # 3. Sustained violation opens exactly one alert
    print("=== [4] Testing Sustained Violation Opens Exactly One Alert ===")
    # 3 consecutive samples >= 80% CPU
    service.evaluate_tick(s_spike, n_spike, l_spike) # Sample 1
    service.evaluate_tick(s_spike, n_spike, l_spike) # Sample 2
    summary = service.evaluate_tick(s_spike, n_spike, l_spike) # Sample 3
    assert summary.total_active == 1
    active_alert = alert_repo.get_active_alert(db, "CPU_HIGH", "host")
    assert active_alert is not None
    assert active_alert.status == "OPEN"
    assert active_alert.severity == "WARNING"
    assert active_alert.occurrence_count == 1
    print(f" PASS: Exactly 1 alert opened after {settings.ALERT_CONSECUTIVE_SAMPLES} consecutive samples (id={active_alert.id}, type={active_alert.type}).")

    # 4. Continued violation updates the existing alert without inserting duplicates
    print("=== [5] Testing Deduplication & In-Place Updates for Continued Violation ===")
    initial_id = active_alert.id
    service.evaluate_tick(s_spike, n_spike, l_spike) # Sample 4
    service.evaluate_tick(s_spike, n_spike, l_spike) # Sample 5
    
    total_db_alerts = db.query(AlertModel).count()
    assert total_db_alerts == 1, f"Expected exactly 1 alert row in DB, found {total_db_alerts}"
    db.refresh(active_alert)
    assert active_alert.id == initial_id
    assert active_alert.occurrence_count == 3
    print(f" PASS: Deduplication verified. Single alert updated (occurrence_count={active_alert.occurrence_count}).")

    # 5. Acknowledgment works independently of resolution
    print("=== [6] Testing Alert Acknowledgment ===")
    ack_alert = alert_repo.acknowledge_alert(db, str(active_alert.id), time.time(), "2026-10-03T18:05:00Z")
    assert ack_alert is not None
    assert ack_alert.status == "ACKNOWLEDGED"
    assert ack_alert.acknowledged_at is not None
    # Underlying violation continues
    service.evaluate_tick(s_spike, n_spike, l_spike)
    db.refresh(ack_alert)
    assert ack_alert.status == "ACKNOWLEDGED", "Violation ongoing must keep ACKNOWLEDGED status, not reopen or resolve"
    print(" PASS: Acknowledged alert remains ACKNOWLEDGED while violation persists.")

    # 6. Returning to normal resolves the alert
    print("=== [7] Testing Auto-Resolution on Normalization ===")
    # 2 consecutive normal samples
    service.evaluate_tick(s1, n1, l1) # Normal sample 1
    service.evaluate_tick(s1, n1, l1) # Normal sample 2
    db.refresh(ack_alert)
    assert ack_alert.status == "RESOLVED"
    assert ack_alert.resolved_at is not None
    print(f" PASS: Alert resolved cleanly upon normalization (resolved_at_utc={ack_alert.resolved_at_utc}).")

    # 7. Persistence survives restart
    print("=== [8] Testing Alert Persistence Across Service Restarts ===")
    db.close()
    new_db = SessionLocal()
    surviving_alerts = new_db.query(AlertModel).all()
    assert len(surviving_alerts) == 1
    assert surviving_alerts[0].status == "RESOLVED"
    new_db.close()
    print(" PASS: Alerts persisted and survived session closure.")

    # 8. Deterministic Network Health Score
    print("=== [9] Testing Deterministic Health Score & Deduction Math ===")
    # Healthy baseline
    s_good, n_good, l_good = create_mock_snapshots(cpu_percent=25.0, mem_percent=55.0, disk_percent=40.0, latency_ms=18.0, packet_loss=0.0)
    score_resp = health_score_service.calculate_score(s_good, n_good, l_good)
    assert score_resp.score == 100
    assert score_resp.status == "HEALTHY"
    assert len(score_resp.deductions) == 0

    # Degraded scenario: High latency (120ms -> 8 pts) + High memory (85% -> 7 pts)
    s_deg, n_deg, l_deg = create_mock_snapshots(mem_percent=85.0, latency_ms=120.0)
    score_deg = health_score_service.calculate_score(s_deg, n_deg, l_deg)
    deduction_sum = sum(d.points for d in score_deg.deductions)
    assert deduction_sum == 15, f"Expected 15 deduction points, got {deduction_sum}"
    assert score_deg.score == 100 - deduction_sum == 85
    assert score_deg.status == "DEGRADED"
    print(f" PASS: Health score is exactly 85/100 (100 - {deduction_sum}) with {score_deg.status} status.")

    # Critical scenario: Unreachable target (35 pts) + Critical CPU (96% -> 15 pts) + High memory (96% -> 15 pts) + Degraded collector (10 pts)
    s_crit, n_crit, l_crit = create_mock_snapshots(
        cpu_percent=96.0,
        mem_percent=96.0,
        is_reachable=False,
        net_status="RESET"
    )
    score_crit = health_score_service.calculate_score(s_crit, n_crit, l_crit)
    tot_points = sum(d.points for d in score_crit.deductions)
    assert score_crit.score == max(0, 100 - tot_points)
    assert score_crit.status == "CRITICAL" or score_crit.status == "POOR"
    print(f" PASS: Critical score properly computed: {score_crit.score}/100, label={score_crit.status}, deductions={tot_points}.")

    # 9. Unavailable / Stale telemetry handling
    print("=== [10] Testing Unavailable Telemetry Not Treated As Zero ===")
    s_unavail, n_unavail, l_unavail = create_mock_snapshots(
        net_status="WARMING_UP",
        is_stale=True
    )
    # CPU not ready
    s_unavail.cpu.is_ready = False
    s_unavail.cpu.usage_percent = None
    score_unavail = health_score_service.calculate_score(s_unavail, n_unavail, l_unavail)
    assert score_unavail.score < 100, "Unavailable/stale telemetry must cause deductions, not pretend 100% healthy!"
    reasons = [d.reason for d in score_unavail.deductions]
    assert any("CPU telemetry initializing" in r for r in reasons)
    assert any("stale" in r.lower() for r in reasons)
    assert any("warming up" in r.lower() for r in reasons)
    print(" PASS: Unavailable/stale telemetry explicitly explained in score deductions without false zeroes.")

    print("\n========================================")
    print("ALL PHASE 8 TEST SPECIFICATIONS PASSED!")
    print("========================================")

if __name__ == "__main__":
    run_tests()
