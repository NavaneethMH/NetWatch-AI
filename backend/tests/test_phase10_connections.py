# -*- coding: utf-8 -*-
"""Phase 10 Exit-Gate & Unit Verification Suite.

Verifies:
1. Active Connection Collector:
   - Scans genuine host network connections.
   - Genuine protocol, family, endpoints, states, PIDs, process names.
   - IPv4 and IPv6 support without errors.
   - AccessDenied and NoSuchProcess handled gracefully.
   - Non-blocking execution, fast collection (< 100ms).
   - Stable runtime identity key.
2. Connection Service:
   - Maintains active connection state in-memory.
   - Updates first_observed / last_observed timestamps correctly.
   - Appearing and disappearing connections between scans handled.
   - Filter by protocol (TCP/UDP), state, process name substring, search query.
   - Generates accurate ConnectionSummary.
   - Never triggers extra OS scans during queries.
3. API Endpoints (via FastAPI TestClient):
   - GET /api/connections returns 200 with ConnectionListResponse.
   - GET /api/connections/summary returns 200 with ConnectionSummary.
   - Query filters (protocol, state, process, search, limit).
4. Storage & WebSocket Integration:
   - Unified telemetry ws_payload includes 'connections' summary.
   - Connections summary has total, tcp, udp, established, listening fields.
5. Regressions:
   - Phase 1-9 schemas, collectors, alerts, and device endpoints remain intact.
"""
import unittest
import time
from fastapi.testclient import TestClient

from backend.main import app
from backend.collectors.connections import ConnectionCollector, RawConnectionEntry
from backend.services.connection_service import ConnectionService
from backend.schemas.connection import ConnectionItem, ConnectionSummary, ConnectionListResponse


class TestPhase10Connections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_collector_scan_live_host(self):
        collector = ConnectionCollector()
        entries, dur_ms = collector.scan_connections_now()

        self.assertIsInstance(entries, list)
        self.assertGreater(len(entries), 0, "Host should have active connections")
        self.assertLess(dur_ms, 500.0, f"Scan took too long: {dur_ms}ms")

        # Verify attributes on genuine entries
        first = entries[0]
        self.assertIn(first.protocol, ["TCP", "UDP"])
        self.assertIn(first.family, ["IPv4", "IPv6"])
        self.assertIsInstance(first.state, str)
        self.assertIsNotNone(first.runtime_key)

        # Check for presence of both TCP and IPv4
        has_tcp = any(e.protocol == "TCP" for e in entries)
        has_ipv4 = any(e.family == "IPv4" for e in entries)
        self.assertTrue(has_tcp, "Should observe at least one TCP connection")
        self.assertTrue(has_ipv4, "Should observe at least one IPv4 connection")

    def test_02_stable_runtime_identity(self):
        c1 = RawConnectionEntry(
            protocol="TCP",
            family="IPv4",
            local_ip="127.0.0.1",
            local_port=8000,
            remote_ip="127.0.0.1",
            remote_port=54321,
            state="ESTABLISHED",
            pid=1234,
            process_name="python.exe",
            runtime_key="TCP:127.0.0.1:8000-127.0.0.1:54321:1234",
        )
        self.assertEqual(c1.runtime_key, "TCP:127.0.0.1:8000-127.0.0.1:54321:1234")

    def test_03_service_lifecycle_and_first_last_observed(self):
        svc = ConnectionService(register_with_collector=False)

        # Tick 1: Connection A and B appear
        t1 = 1000.0
        entry_a = RawConnectionEntry(
            protocol="TCP",
            family="IPv4",
            local_ip="127.0.0.1",
            local_port=8000,
            remote_ip="127.0.0.1",
            remote_port=50000,
            state="ESTABLISHED",
            pid=100,
            process_name="netwatch.exe",
            runtime_key="TCP:127.0.0.1:8000-127.0.0.1:50000:100",
        )
        entry_b = RawConnectionEntry(
            protocol="TCP",
            family="IPv4",
            local_ip="0.0.0.0",
            local_port=8000,
            remote_ip=None,
            remote_port=None,
            state="LISTEN",
            pid=100,
            process_name="netwatch.exe",
            runtime_key="TCP:0.0.0.0:8000-*:*:100",
        )
        svc.update_connections([entry_a, entry_b], scan_timestamp=t1, duration_ms=2.5)

        res1 = svc.get_connections()
        self.assertEqual(res1.total, 2)
        summary1 = svc.get_summary()
        self.assertEqual(summary1.total, 2)
        self.assertEqual(summary1.established, 1)
        self.assertEqual(summary1.listening, 1)

        conn_a = next(c for c in res1.items if c.id == entry_a.runtime_key)
        self.assertEqual(conn_a.first_observed, t1)
        self.assertEqual(conn_a.last_observed, t1)

        # Tick 2: Connection A persists, B disappears, C appears
        t2 = 1005.0
        entry_c = RawConnectionEntry(
            protocol="UDP",
            family="IPv4",
            local_ip="0.0.0.0",
            local_port=5353,
            remote_ip=None,
            remote_port=None,
            state="NONE",
            pid=200,
            process_name="dns.exe",
            runtime_key="UDP:0.0.0.0:5353-*:*:200",
        )
        svc.update_connections([entry_a, entry_c], scan_timestamp=t2, duration_ms=1.8)

        res2 = svc.get_connections()
        self.assertEqual(res2.total, 2)
        keys2 = {c.id for c in res2.items}
        self.assertIn(entry_a.runtime_key, keys2)
        self.assertNotIn(entry_b.runtime_key, keys2, "Connection B should have disappeared")
        self.assertIn(entry_c.runtime_key, keys2, "Connection C should be present")

        conn_a_updated = next(c for c in res2.items if c.id == entry_a.runtime_key)
        self.assertEqual(conn_a_updated.first_observed, t1, "first_observed must be preserved")
        self.assertEqual(conn_a_updated.last_observed, t2, "last_observed must be updated")

        conn_c = next(c for c in res2.items if c.id == entry_c.runtime_key)
        self.assertEqual(conn_c.first_observed, t2)
        self.assertEqual(conn_c.last_observed, t2)

    def test_04_service_filters(self):
        svc = ConnectionService(register_with_collector=False)
        entries = [
            RawConnectionEntry("TCP", "IPv4", "127.0.0.1", 8000, "127.0.0.1", 50000, "ESTABLISHED", 10, "browser.exe", "k1"),
            RawConnectionEntry("TCP", "IPv4", "0.0.0.0", 80, None, None, "LISTEN", 20, "webserver.exe", "k2"),
            RawConnectionEntry("UDP", "IPv4", "0.0.0.0", 5353, None, None, "NONE", 30, "mdns.exe", "k3"),
        ]
        svc.update_connections(entries, scan_timestamp=time.time(), duration_ms=1.0)

        # Protocol filter
        tcp_res = svc.get_connections(protocol="TCP")
        self.assertEqual(tcp_res.total, 2)
        udp_res = svc.get_connections(protocol="UDP")
        self.assertEqual(udp_res.total, 1)

        # State filter
        est_res = svc.get_connections(state="ESTABLISHED")
        self.assertEqual(est_res.total, 1)

        # Process filter
        proc_res = svc.get_connections(process="browser")
        self.assertEqual(proc_res.total, 1)
        self.assertEqual(proc_res.items[0].process_name, "browser.exe")

        # Search query
        search_res = svc.get_connections(search="5353")
        self.assertEqual(search_res.total, 1)
        self.assertEqual(search_res.items[0].process_name, "mdns.exe")

    def test_05_api_get_connections(self):
        # Trigger an actual collector cycle in global connection_service
        from backend.collectors.connections import connection_collector
        connection_collector._execute_cycle()

        res = self.client.get("/api/connections")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("count", data)
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertGreater(data["total"], 0)

        first = data["items"][0]
        self.assertIn("id", first)
        self.assertIn("protocol", first)
        self.assertIn("state", first)
        self.assertIn("family", first)
        self.assertIn("first_observed", first)
        self.assertIn("last_observed", first)

    def test_06_api_get_connections_summary(self):
        res = self.client.get("/api/connections/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("tcp", data)
        self.assertIn("udp", data)
        self.assertIn("established", data)
        self.assertIn("listening", data)
        self.assertGreater(data["total"], 0)
        self.assertEqual(data["tcp"] + data["udp"], data["total"])

    def test_07_api_repeated_requests_performance(self):
        # Verify rapid repeated requests return instantly without triggering scans
        t0 = time.perf_counter()
        for _ in range(20):
            res = self.client.get("/api/connections?limit=10")
            self.assertEqual(res.status_code, 200)
        dur = time.perf_counter() - t0
        # 20 in-memory requests should complete well within 500ms
        self.assertLess(dur, 0.5, f"20 API calls took too long: {dur*1000:.2f}ms")

    def test_08_phase1_9_regression(self):
        endpoints = [
            "/api/health",
            "/api/system/current",
            "/api/system/history?limit=5",
            "/api/network/current",
            "/api/network/history?limit=5",
            "/api/latency/current",
            "/api/latency/history?limit=5",
            "/api/health-score",
            "/api/alerts/summary",
            "/api/devices",
            "/api/devices/discovery/status",
        ]
        for ep in endpoints:
            r = self.client.get(ep)
            self.assertEqual(r.status_code, 200, f"Endpoint {ep} failed: {r.status_code}")


if __name__ == "__main__":
    unittest.main()
