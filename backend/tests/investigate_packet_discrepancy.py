"""
Investigation script for Stage C:
Investigate why 'all' versus '1h'/'24h' had a discrepancy of 88,868 vs 88,893 packets.
"""

import sqlite3
import time
from backend.services.analytics_service import _raw_conn, _resolve_window

conn = _raw_conn()
cur = conn.cursor()

print("=== 1. Summary of protocol_metrics table ===")
cur.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp), SUM(total_packets) FROM protocol_metrics")
row = cur.fetchone()
print(f"Total rows: {row[0]}, Min TS: {row[1]}, Max TS: {row[2]}, Sum total_packets: {row[3]}")

cur.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp), SUM(total_packets) FROM protocol_metrics WHERE status = 'LIVE'")
row_live = cur.fetchone()
print(f"LIVE rows: {row_live[0]}, Min TS: {row_live[1]}, Max TS: {row_live[2]}, Sum total_packets: {row_live[3]}")

print("\n=== 2. Summary of network_metrics table ===")
cur.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM network_metrics")
nrow = cur.fetchone()
print(f"Total rows: {nrow[0]}, Min TS: {nrow[1]}, Max TS: {nrow[2]}")

print("\n=== 3. Earliest rows in protocol_metrics vs network_metrics ===")
cur.execute("SELECT id, timestamp, total_packets, status FROM protocol_metrics ORDER BY timestamp ASC LIMIT 5")
for r in cur.fetchall():
    print("  Proto row:", dict(r))

cur.execute("SELECT id, timestamp, status FROM network_metrics ORDER BY timestamp ASC LIMIT 5")
for r in cur.fetchall():
    print("  Net row:  ", dict(r))

print("\n=== 4. Evaluate _resolve_window('all') ===")
s_all, e_all = _resolve_window("all", None, None)
s_1h, e_1h = _resolve_window("1h", None, None)
s_24h, e_24h = _resolve_window("24h", None, None)
print(f"all range: start={s_all:.2f}, end={e_all:.2f}")
print(f"1h  range: start={s_1h:.2f}, end={e_1h:.2f}")
print(f"24h range: start={s_24h:.2f}, end={e_24h:.2f}")

cur.execute("SELECT COUNT(*), SUM(total_packets) FROM protocol_metrics WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'", (s_all, e_all))
res_all = cur.fetchone()
print(f"All window in protocol_metrics: rows={res_all[0]}, sum_packets={res_all[1]}")

cur.execute("SELECT COUNT(*), SUM(total_packets) FROM protocol_metrics WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'", (s_24h, e_24h))
res_24h = cur.fetchone()
print(f"24h window in protocol_metrics: rows={res_24h[0]}, sum_packets={res_24h[1]}")

# Rows in protocol_metrics that have timestamp < s_all
cur.execute("SELECT id, timestamp, total_packets FROM protocol_metrics WHERE timestamp < ?", (s_all,))
older_proto = cur.fetchall()
print(f"Protocol rows older than s_all ({s_all}): {len(older_proto)}")
for p in older_proto:
    print("  Older proto row:", dict(p))

conn.close()
