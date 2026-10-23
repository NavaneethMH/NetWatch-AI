"""
Benchmark index performance: status index vs timestamp index on protocol_metrics.
"""

import sqlite3
import time
from backend.services.analytics_service import _raw_conn

conn = _raw_conn()
cur = conn.cursor()

# 1. Check sqlite_stat tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sqlite_stat%'")
stats = cur.fetchall()
print("sqlite_stat tables:", [dict(s) for s in stats])

# 2. Benchmark 500 runs using status index vs timestamp index
s_ts = time.time() - 300
e_ts = time.time()

t0 = time.perf_counter()
for _ in range(500):
    cur.execute(
        "SELECT timestamp, packets_per_second, total_packets FROM protocol_metrics "
        "WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE' ORDER BY timestamp ASC",
        (s_ts, e_ts)
    )
    _ = cur.fetchall()
t_default = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
for _ in range(500):
    cur.execute(
        "SELECT timestamp, packets_per_second, total_packets FROM protocol_metrics "
        "INDEXED BY ix_protocol_metrics_timestamp "
        "WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE' ORDER BY timestamp ASC",
        (s_ts, e_ts)
    )
    _ = cur.fetchall()
t_forced_ts = (time.perf_counter() - t0) * 1000

print(f"500 executions with default (status index):   {t_default:.2f} ms ({t_default/500:.3f} ms/query)")
print(f"500 executions with forced timestamp index:  {t_forced_ts:.2f} ms ({t_forced_ts/500:.3f} ms/query)")

conn.close()
