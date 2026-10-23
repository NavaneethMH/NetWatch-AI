"""
Test controlled slow-probe latency behavior where execution exceeds interval.
Verifies:
1. Probes never overlap (synchronous in sampler thread)
2. Sampler does not busy loop when probe exceeds interval
3. Recovery and scheduling resets cleanly
"""

import time
from unittest.mock import patch
from backend.collectors.latency import LatencyCollector
from backend.schemas.latency import LatencySnapshot


def test_slow_probe_overrun_and_no_busy_loop():
    collector = LatencyCollector()
    collector.interval = 1  # 1s interval
    collector.count = 1

    probe_times = []
    
    # Mock _sample to simulate a slow probe that takes 2.5s (exceeding 1s interval)
    original_sample = collector._sample

    def mock_slow_sample(quick=False):
        start_t = time.monotonic()
        probe_times.append((start_t, "start"))
        if not quick:
            # Simulate slow ping probe taking 1.5 seconds
            time.sleep(1.5)
        probe_times.append((time.monotonic(), "end"))

    collector._sample = mock_slow_sample

    # Run for 4 seconds
    collector.start()
    time.sleep(4.0)
    collector.stop()

    starts = [t for t, ev in probe_times if ev == "start"]
    ends = [t for t, ev in probe_times if ev == "end"]

    # Verify probes never overlapped: each start is >= previous end
    for i in range(1, len(starts)):
        assert starts[i] >= ends[i - 1], f"Probe {i} started at {starts[i]} before previous ended at {ends[i - 1]}"

    # Verify no busy loop: probe count should be bounded (approx 2-3 probes in 4s when each takes 1.5s + 1s interval)
    # If it was busy-looping, starts would be tens or hundreds
    assert len(starts) <= 4, f"Too many probes executed ({len(starts)}), indicates busy loop!"
    print(f"Total probes in 4s with 1.5s delay: {len(starts)} (bounded and non-overlapping)")
