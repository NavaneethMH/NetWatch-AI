"""
Task 1 Audit: Detailed index inspection and EXPLAIN QUERY PLAN analysis on protocol_metrics.
"""

import sqlite3
import time
from backend.services.analytics_service import _raw_conn

conn = _raw_conn()
cur = conn.cursor()

print("=== 1. Inspect existing indexes on protocol_metrics ===")
cur.execute("PRAGMA index_list(protocol_metrics)")
indexes = cur.fetchall()
for idx in indexes:
    print("  Index:", dict(idx))
    cur.execute(f"PRAGMA index_info({dict(idx)['name']})")
    for col in cur.fetchall():
        print("    Column:", dict(col))

# Actual queries from analytics_service.py
start_ts = time.time() - 3600
end_ts = time.time()

print("\n=== 2. EXPLAIN QUERY PLAN for get_timeseries protocol query ===")
sql_ts = """
EXPLAIN QUERY PLAN
SELECT timestamp, packets_per_second, total_packets,
       tcp_packets, udp_packets, icmp_packets, dns_packets,
       ipv4_packets, ipv6_packets
FROM protocol_metrics
WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'
ORDER BY timestamp ASC
"""
cur.execute(sql_ts, (start_ts, end_ts))
for row in cur.fetchall():
    print(" ", dict(row))

print("\n=== 3. EXPLAIN QUERY PLAN for get_report protocol aggregation query ===")
sql_rep1 = """
EXPLAIN QUERY PLAN
SELECT packets_per_second,
       SUM(total_packets) as total_p,
       SUM(tcp_packets) as tcp_p,
       SUM(udp_packets) as udp_p,
       SUM(icmp_packets) as icmp_p,
       SUM(dns_packets) as dns_p,
       SUM(ipv4_packets) as ipv4_p,
       SUM(ipv6_packets) as ipv6_p
FROM protocol_metrics
WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'
"""
cur.execute(sql_rep1, (start_ts, end_ts))
for row in cur.fetchall():
    print(" ", dict(row))

print("\n=== 4. EXPLAIN QUERY PLAN when forcing timestamp index vs status index ===")
sql_force_ts = """
EXPLAIN QUERY PLAN
SELECT timestamp, packets_per_second, total_packets
FROM protocol_metrics INDEXED BY ix_protocol_metrics_timestamp
WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'
ORDER BY timestamp ASC
"""
try:
    cur.execute(sql_force_ts, (start_ts, end_ts))
    for row in cur.fetchall():
        print("  INDEXED BY timestamp:", dict(row))
except Exception as e:
    print("  Error with INDEXED BY timestamp:", e)

# Row counts by status
cur.execute("SELECT status, COUNT(*) FROM protocol_metrics GROUP BY status")
print("\n=== 5. Distribution of status in protocol_metrics ===")
for r in cur.fetchall():
    print(" ", dict(r))

conn.close()
