"""
Phase 12 Historical Analytics & Reporting Backend Tests
Validates the /api/analytics endpoints and underlying service logic.
"""

import pytest
from backend.services.analytics_service import analytics_service
from backend.schemas.analytics import AnalyticsCoverage, TimeSeriesResponse, AnalyticsReport


def test_coverage_service():
    """Verify that get_coverage returns valid table metadata and non-negative counts."""
    cov = analytics_service.get_coverage()
    assert isinstance(cov, AnalyticsCoverage)
    assert len(cov.tables) > 0

    table_names = [t.table for t in cov.tables]
    # Check expected core tables are reported
    for expected in ["system_metrics", "network_metrics", "interface_metrics", "latency_metrics", "protocol_metrics"]:
        assert expected in table_names

    for t in cov.tables:
        assert t.row_count >= 0
        if t.row_count > 0:
            assert t.oldest_ts is not None
            assert t.newest_ts is not None
            assert t.oldest_ts <= t.newest_ts
            if t.span_seconds is not None:
                assert t.span_seconds >= 0.0


@pytest.mark.parametrize("range_key,expected_max_bucket", [
    ("5m", 10),
    ("15m", 30),
    ("1h", 60),
    ("6h", 300),
    ("24h", 900),
    ("7d", 3600),
    ("all", 86400),
])
def test_timeseries_service_ranges(range_key, expected_max_bucket):
    """Verify timeseries returns valid bucketed points and valid timestamp ranges."""
    res = analytics_service.get_timeseries(range_key=range_key)
    assert isinstance(res, TimeSeriesResponse)
    assert res.from_ts <= res.to_ts
    assert res.bucket_seconds >= 1
    assert res.point_count == len(res.points)

    # Check structure of points if non-empty
    for pt in res.points:
        assert pt.bucket_ts >= res.from_ts - res.bucket_seconds
        assert pt.bucket_ts <= res.to_ts + res.bucket_seconds
        # Numbers or None
        if pt.download_mbps is not None:
            assert pt.download_mbps >= 0
        if pt.cpu_percent is not None:
            assert 0 <= pt.cpu_percent <= 100


def test_report_service():
    """Verify aggregated summary report calculations."""
    report = analytics_service.get_report(range_key="24h")
    assert isinstance(report, AnalyticsReport)
    assert report.from_ts < report.to_ts
    assert report.window_seconds > 0

    # Check metrics structure
    for field_name in ["download_mbps", "upload_mbps", "cpu_percent", "memory_percent", "latency_avg_ms", "packet_loss_percent", "pps"]:
        agg = getattr(report, field_name)
        assert agg.sample_count >= 0
        if agg.sample_count > 0:
            assert agg.min is not None
            assert agg.max is not None
            assert agg.avg is not None
            assert agg.min <= agg.max
            assert agg.min <= agg.avg <= agg.max
            assert agg.p95 is not None

    assert report.total_packets >= 0
    assert report.total_alerts >= 0
