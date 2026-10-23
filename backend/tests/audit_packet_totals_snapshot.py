"""
Task 2 Audit: Verify packet totals and window resolution against persisted rows
within an isolated, consistent SQLite read transaction.
"""

import sqlite3
import time
from backend.services.analytics_service import _raw_conn, _resolve_window, get_report

conn = _raw_conn()
# Ensure transaction isolation
conn.isolation_level = "DEFERRED"
cur = conn.cursor()

print("=== Task 2 Verification: Snapshot Read Consistency ===")
cur.execute("BEGIN TRANSACTION")

# 1. Measure min/max across all tables
cur.execute("""
    SELECT MIN(min_ts) FROM (
        SELECT MIN(timestamp) as min_ts FROM network_metrics
        UNION ALL
        SELECT MIN(timestamp) as min_ts FROM protocol_metrics
        UNION ALL
        SELECT MIN(timestamp) as min_ts FROM system_metrics
    ) WHERE min_ts IS NOT NULL AND min_ts > 0
""")
global_oldest = cur.fetchone()[0]
print(f"Global oldest timestamp across telemetry tables: {global_oldest}")

# Oldest specifically in protocol_metrics
cur.execute("SELECT MIN(timestamp), COUNT(*), SUM(total_packets) FROM protocol_metrics WHERE status = 'LIVE'")
p_oldest, p_count, p_sum_packets = cur.fetchone()
print(f"protocol_metrics (LIVE): min_ts={p_oldest}, count={p_count}, sum_packets={p_sum_packets}")

# 2. Check _resolve_window('all')
s_all, e_all = _resolve_window("all", None, None)
print(f"_resolve_window('all'): start={s_all}, end={e_all}")
assert s_all <= p_oldest, f"s_all ({s_all}) is greater than p_oldest ({p_oldest}), would clip data!"

# Query protocol rows within s_all..e_all
cur.execute(
    "SELECT COUNT(*), SUM(total_packets) FROM protocol_metrics WHERE timestamp >= ? AND timestamp <= ? AND status = 'LIVE'",
    (s_all, e_all)
)
p_all_count, p_all_packets = cur.fetchone()
print(f"Rows matching s_all..e_all: count={p_all_count}, sum_packets={p_all_packets}")

# 3. Compare with get_report('all') directly
rep_all = get_report(range_key="all")
print(f"get_report('all') returned: total_packets={rep_all.total_packets}")

# Verify exact match
assert rep_all.total_packets == p_all_packets, f"Report {rep_all.total_packets} != Persisted {p_all_packets}"
assert p_all_count == p_count, f"Clipped rows! Expected {p_count}, got {p_all_count}"
assert p_all_packets == p_sum_packets, f"Clipped packets! Expected {p_sum_packets}, got {p_all_packets}"

# 4. Compare with 24h report if database is < 24h old
rep_24h = get_report(range_key="24h")
print(f"get_report('24h') returned: total_packets={rep_24h.total_packets}")
assert rep_all.total_packets == rep_24h.total_packets, f"Mismatch: all={rep_all.total_packets} vs 24h={rep_24h.total_packets}"

print(">>> [PASS] Packet totals between 'all' and '24h' exactly match persisted rows without discrepancy.")
cur.execute("COMMIT")
conn.close()
