import requests
import json

BASE = "http://127.0.0.1:8000"
RANGES = ["5m", "15m", "1h", "6h", "24h", "7d", "all"]

print("=== 1. Live API /api/analytics/timeseries ===")
for r in RANGES:
    res = requests.get(f"{BASE}/api/analytics/timeseries", params={"range": r}, timeout=10)
    assert res.status_code == 200, f"Failed {r}: {res.text}"
    d = res.json()
    pts = d.get("points", [])
    # Check ordering
    ts_list = [p["bucket_ts"] for p in pts]
    is_sorted = ts_list == sorted(ts_list)
    print(f"range={r:4s} | status=200 | points={d['point_count']:3d} | bucket={d['bucket_seconds']:4d}s | from={d['from_utc']} | to={d['to_utc']} | sorted={is_sorted}")

inv_ts = requests.get(f"{BASE}/api/analytics/timeseries", params={"range": "invalid_range"}, timeout=10)
print(f"range=invalid_range | status={inv_ts.status_code} | response={inv_ts.json()}")

print("\n=== 2. Live API /api/analytics/report ===")
for r in RANGES:
    res = requests.get(f"{BASE}/api/analytics/report", params={"range": r}, timeout=10)
    assert res.status_code == 200, f"Failed {r}: {res.text}"
    d = res.json()
    dl = d.get("download_mbps", {})
    print(f"range={r:4s} | status=200 | window={d['window_human']:6s} | dl_samples={dl.get('sample_count', 0):4d} | dl_avg={dl.get('avg')} | total_packets={d.get('total_packets', 0):6d}")

inv_rep = requests.get(f"{BASE}/api/analytics/report", params={"range": "invalid_range"}, timeout=10)
print(f"range=invalid_range | status={inv_rep.status_code} | response={inv_rep.json()}")
