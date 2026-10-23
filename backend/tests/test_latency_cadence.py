import sys
sys.path.insert(0, r'c:\Users\navan\OneDrive\Desktop\NetWatch AI')

import time
import numpy as np
from backend.collectors.latency import LatencyCollector
from backend.schemas.latency import LatencySnapshot

def benchmark_latency_cadence():
    print("=== BENCHMARKING LATENCY SAMPLING CADENCE ===")
    probes = []
    
    def on_probe(snap: LatencySnapshot):
        t = time.monotonic()
        probes.append((t, snap))
        print(f"  Probe {len(probes)}: target={snap.target}, status={snap.status}, avg_ms={snap.latency_avg_ms}, mono_ts={t:.3f}")

    collector = LatencyCollector()
    collector.register_callback(on_probe)
    
    # Run for 22 seconds (initial quick probe + ~4 periodic probes at 5s start-to-start)
    print("Starting collector for 22 seconds...")
    collector.start()
    time.sleep(22.0)
    collector.stop()
    print(f"Collector stopped. Total probes collected: {len(probes)}")
    
    if len(probes) >= 3:
        # Disregard the initial warmup probe (index 0) and evaluate periodic start-to-start intervals
        periodic_timestamps = [p[0] for p in probes[1:]]
        intervals = np.diff(periodic_timestamps)
        print("\n--- Periodic Probe Interval Statistics (start-to-start) ---")
        print(f"  Recorded intervals (seconds): {[round(i, 3) for i in intervals]}")
        print(f"  Min interval:    {np.min(intervals):.3f}s")
        print(f"  Mean interval:   {np.mean(intervals):.3f}s")
        print(f"  Median interval: {np.median(intervals):.3f}s")
        print(f"  Max interval:    {np.max(intervals):.3f}s")

def test_unreachable_and_slow_probe():
    print("\n=== TESTING UNREACHABLE TARGET HANDLING ===")
    collector = LatencyCollector()
    collector.target = "192.0.2.1"  # RFC 5737 TEST-NET-1 (unroutable/unreachable)
    collector.interval = 2
    collector.count = 1
    
    probes = []
    collector.register_callback(lambda snap: probes.append(snap))
    collector.start()
    time.sleep(3.0)
    collector.stop()
    
    if probes:
        last = probes[-1]
        print(f"  Unreachable probe status: {last.status} (expected: UNREACHABLE)")
        print(f"  Packet loss: {last.packet_loss_percent}% (expected: 100.0%)")
        print(f"  Reachable: {last.is_reachable} (expected: False)")
        assert last.status == "UNREACHABLE"
        assert last.is_reachable is False
        assert last.packet_loss_percent == 100.0
        print("  [PASS] Unreachable status semantics preserved.")

if __name__ == '__main__':
    benchmark_latency_cadence()
    test_unreachable_and_slow_probe()
