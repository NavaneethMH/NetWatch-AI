import sqlite3
import time
from backend.services.analytics_service import _raw_conn

conn = _raw_conn()
cur = conn.cursor()

queries = [
    ("System metrics", "EXPLAIN QUERY PLAN SELECT timestamp, cpu_percent FROM system_metrics WHERE timestamp >= ? AND timestamp <= ?"),
    ("Network metrics", "EXPLAIN QUERY PLAN SELECT timestamp, download_mbps FROM network_metrics WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'"),
    ("Latency metrics", "EXPLAIN QUERY PLAN SELECT timestamp, latency_avg_ms FROM latency_metrics WHERE timestamp >= ? AND timestamp <= ?"),
    ("Protocol metrics", "EXPLAIN QUERY PLAN SELECT timestamp, packets_per_second FROM protocol_metrics WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'"),
    ("Alerts", "EXPLAIN QUERY PLAN SELECT COUNT(*), severity FROM alerts WHERE opened_at >= ? AND opened_at <= ? GROUP BY severity"),
]

print("=== SQLite Query Plans ===")
for name, q in queries:
    cur.execute(q, (0, 9999999999))
    plan = cur.fetchall()
    print(f"--- {name} ---")
    for row in plan:
        print(" ", dict(row))

conn.close()
