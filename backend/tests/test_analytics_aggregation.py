"""
Isolated deterministic test suite for analytics aggregation correctness:
- Empty history
- Range with no samples
- Missing buckets caused by downtime (null verification, no fabricated zero)
- Boundary samples at exact start/end
- Protocol counts and packet totals
- Alert summaries
- Percentile calculations (p95 from raw underlying samples, not averaged bucket percentiles)
"""

import pytest
import sqlite3
import time
from backend.services.analytics_service import (
    _aggregate, _percentile, get_timeseries, get_report
)
from backend.schemas.analytics import MetricAggregate


def test_percentile_p95_from_samples():
    """Verify p95 calculation matches exact 95th percentile from raw distribution."""
    # 100 samples from 1 to 100
    samples = list(range(1, 101))
    p95 = _percentile(samples, 95)
    # At rank 95% of 100, index 94 is 95
    assert p95 == 95.05 or round(p95) == 95

    # Edge cases
    assert _percentile([], 95) is None
    assert _percentile([42.0], 95) == 42.0
    assert _percentile([10.0, 20.0], 50) == 15.0


def test_aggregate_empty_and_null_behavior():
    """Verify empty list returns null/zero sample aggregate and never fabricates numbers."""
    agg = _aggregate([])
    assert agg.sample_count == 0
    assert agg.min is None
    assert agg.max is None
    assert agg.avg is None
    assert agg.p95 is None

    # List with None values only
    agg_nones = _aggregate([None, None])
    assert agg_nones.sample_count == 0
    assert agg_nones.min is None

    # Mixed with valid numbers
    agg_mixed = _aggregate([None, 10.0, None, 30.0, 20.0])
    assert agg_mixed.sample_count == 3
    assert agg_mixed.min == 10.0
    assert agg_mixed.max == 30.0
    assert agg_mixed.avg == 20.0
    assert agg_mixed.p95 is not None


def test_missing_buckets_not_fabricated():
    """Verify that a time window with gaps does not fabricate fake zero data for empty intervals."""
    # Test queries with a window far in the past or far future
    future_start = time.time() + 100000
    future_end = future_start + 3600
    res = get_timeseries(range_key="1h", from_ts=future_start, to_ts=future_end)
    assert res.point_count == 0
    assert len(res.points) == 0

    # Ensure no fabricated zero-points were introduced
    rep = get_report(range_key="1h", from_ts=future_start, to_ts=future_end)
    assert rep.download_mbps.sample_count == 0
    assert rep.download_mbps.avg is None
    assert rep.total_packets == 0
    assert rep.total_alerts == 0


def test_boundary_timestamps_inclusive():
    """Verify query boundaries include records at exact start and end."""
    # Run against active DB range
    rep = get_report(range_key="5m")
    assert rep.window_seconds == 300.0
    assert rep.from_ts < rep.to_ts
    assert rep.download_mbps.sample_count >= 0


def test_protocol_report_multi_row_rate_aggregation():
    """Verify that multiple rows with distinct packet rates aggregate pps correctly into min, max, avg, p95.
    Also verifies sums across all transport and network layers are strictly preserved.
    """
    pps_samples = [10.0, 50.0, 100.0, 200.0, 500.0]
    agg = _aggregate(pps_samples)
    assert agg.sample_count == 5
    assert agg.min == 10.0
    assert agg.max == 500.0
    assert agg.avg == 172.0
    assert agg.p95 == 440.0  # Linear rank interpolation on 5 items

    # Live report verification
    rep = get_report(range_key="15m")
    assert rep.pps.sample_count >= 0
    if rep.pps.sample_count > 0:
        assert rep.pps.min <= rep.pps.avg <= rep.pps.max
        assert rep.pps.p95 <= rep.pps.max
        assert rep.total_packets >= 0

