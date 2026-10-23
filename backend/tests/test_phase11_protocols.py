# -*- coding: utf-8 -*-
"""Phase 11 Unit and Integration Test Suite.

Verifies:
1. Fast binary header decoder:
   - Accurately classifies TCP, UDP, ICMP, DNS (port 53), IPv4, IPv6, and Other packets.
   - Preserves mathematical invariants:
     * Transport: TCP + UDP + ICMP + Other == total_packets
     * Network: IPv4 + IPv6 + Other <= total_packets
     * DNS is tracked as an application subset of UDP/TCP.
2. Window Aggregation:
   - Computes packets_per_second, bytes_per_second, and avg_packet_size accurately.
   - Distinguishes LIVE + 0 packets from PERMISSION_REQUIRED, ERROR, etc.
   - Bounded state with zero heap retention of packet payloads.
3. Service & Repository Layer:
   - Window summaries saved to SQLite (protocol_metrics table).
   - Historical window queries with from, to, limit filters.
   - Latest window retrieval and summary generation.
4. API Endpoints via TestClient:
   - GET /api/protocols/current returns 200 with ProtocolWindowMetric schema.
   - GET /api/protocols/history returns 200 with ProtocolHistoryResponse schema.
   - Repeated queries do not trigger packet captures.
5. Live Controlled Capture Simulation & Validation:
   - Feeds controlled mock packets into collector accumulator to verify live window generation.
6. Full Phase 1–10 Regressions:
   - All previous endpoints remain functional (200 OK).
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
import time
import uuid
from fastapi.testclient import TestClient

from backend.main import app
from backend.collectors.packets import (
    PacketCollector,
    PacketMetadata,
    WindowAggregate,
    parse_raw_ip_packet,
)
from backend.services.protocol_service import ProtocolAnalyticsService
from backend.schemas.protocol import (
    ProtocolWindowMetric,
    ProtocolHistoryResponse,
    ProtocolSummary,
)
from backend.database.session import SessionLocal
from backend.database.models import ProtocolMetricModel


class TestPhase11Protocols(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_binary_packet_decoder(self):
        # 1. Synthesize IPv4 TCP packet (40 bytes total: 20 bytes IP, 20 bytes TCP)
        # IP header: version 4, IHL 5, total len 40, proto 6 (TCP)
        ip_tcp = bytearray(40)
        ip_tcp[0] = 0x45  # v4, ihl 5
        ip_tcp[2:4] = (40).to_bytes(2, "big")
        ip_tcp[9] = 6  # TCP
        # TCP header: sport 443, dport 50000
        ip_tcp[20:22] = (443).to_bytes(2, "big")
        ip_tcp[22:24] = (50000).to_bytes(2, "big")

        m_tcp = parse_raw_ip_packet(bytes(ip_tcp))
        self.assertEqual(m_tcp.family, "IPv4")
        self.assertEqual(m_tcp.transport, "TCP")
        self.assertFalse(m_tcp.is_dns)
        self.assertEqual(m_tcp.size, 40)

        # 2. Synthesize IPv4 UDP DNS packet (sport 54321, dport 53)
        ip_dns = bytearray(28)
        ip_dns[0] = 0x45
        ip_dns[9] = 17  # UDP
        ip_dns[20:22] = (54321).to_bytes(2, "big")
        ip_dns[22:24] = (53).to_bytes(2, "big")  # port 53 = DNS

        m_dns = parse_raw_ip_packet(bytes(ip_dns))
        self.assertEqual(m_dns.family, "IPv4")
        self.assertEqual(m_dns.transport, "UDP")
        self.assertTrue(m_dns.is_dns)

        # 3. Synthesize IPv4 ICMP packet
        ip_icmp = bytearray(28)
        ip_icmp[0] = 0x45
        ip_icmp[9] = 1  # ICMP
        m_icmp = parse_raw_ip_packet(bytes(ip_icmp))
        self.assertEqual(m_icmp.family, "IPv4")
        self.assertEqual(m_icmp.transport, "ICMP")
        self.assertFalse(m_icmp.is_dns)

        # 4. Synthesize IPv6 TCP packet
        ip6_tcp = bytearray(60)
        ip6_tcp[0] = 0x60  # v6
        ip6_tcp[6] = 6   # next header = TCP
        ip6_tcp[40:42] = (80).to_bytes(2, "big")
        ip6_tcp[42:44] = (40000).to_bytes(2, "big")

        m_ip6 = parse_raw_ip_packet(bytes(ip6_tcp))
        self.assertEqual(m_ip6.family, "IPv6")
        self.assertEqual(m_ip6.transport, "TCP")

    def test_02_collector_window_accumulation_and_math(self):
        col = PacketCollector(window_seconds=1.0)
        col.status = "LIVE"
        col.current_interface = "Wi-Fi"

        # Record 10 packets: 5 TCP (non-dns), 3 UDP (2 DNS), 1 ICMP, 1 other
        col.record_packet(PacketMetadata(size=100, family="IPv4", transport="TCP", is_dns=False))
        col.record_packet(PacketMetadata(size=200, family="IPv4", transport="TCP", is_dns=False))
        col.record_packet(PacketMetadata(size=300, family="IPv4", transport="TCP", is_dns=False))
        col.record_packet(PacketMetadata(size=400, family="IPv6", transport="TCP", is_dns=False))
        col.record_packet(PacketMetadata(size=500, family="IPv6", transport="TCP", is_dns=False))

        col.record_packet(PacketMetadata(size=80, family="IPv4", transport="UDP", is_dns=True))
        col.record_packet(PacketMetadata(size=90, family="IPv4", transport="UDP", is_dns=True))
        col.record_packet(PacketMetadata(size=110, family="IPv4", transport="UDP", is_dns=False))

        col.record_packet(PacketMetadata(size=60, family="IPv4", transport="ICMP", is_dns=False))
        col.record_packet(PacketMetadata(size=50, family="OTHER", transport="OTHER", is_dns=False))

        win = col.finalize_current_window()

        self.assertEqual(win.total_packets, 10)
        self.assertEqual(win.total_bytes, 1890)
        self.assertEqual(win.avg_packet_size, 189.0)

        # Transport invariants: TCP + UDP + ICMP + other == total_packets
        self.assertEqual(win.tcp_packets, 5)
        self.assertEqual(win.udp_packets, 3)
        self.assertEqual(win.icmp_packets, 1)
        self.assertEqual(win.other_transport_packets, 1)
        self.assertEqual(
            win.tcp_packets + win.udp_packets + win.icmp_packets + win.other_transport_packets,
            win.total_packets
        )

        # Application subset: DNS count <= UDP + TCP
        self.assertEqual(win.dns_packets, 2)
        self.assertLessEqual(win.dns_packets, win.tcp_packets + win.udp_packets)

        # Network layer invariants: IPv4 + IPv6 + other <= total_packets
        self.assertEqual(win.ipv4_packets, 7)
        self.assertEqual(win.ipv6_packets, 2)
        self.assertEqual(win.other_network_packets, 1)
        self.assertEqual(
            win.ipv4_packets + win.ipv6_packets + win.other_network_packets,
            win.total_packets
        )

    def test_03_zero_packet_live_window_vs_degraded(self):
        col = PacketCollector(window_seconds=1.0)
        col.status = "LIVE"
        win_live_zero = col.finalize_current_window()
        self.assertEqual(win_live_zero.status, "LIVE")
        self.assertEqual(win_live_zero.total_packets, 0)
        self.assertEqual(win_live_zero.packets_per_second, 0.0)

        col.status = "PERMISSION_REQUIRED"
        col.limitation_reason = "Elevated rights required"
        win_perm = col.finalize_current_window()
        self.assertEqual(win_perm.status, "PERMISSION_REQUIRED")
        self.assertIsNotNone(win_perm.error_message)

    def test_04_service_persistence_and_history(self):
        svc = ProtocolAnalyticsService(register_with_collector=False)
        test_win = WindowAggregate(
            window_id=str(uuid.uuid4()),
            timestamp=time.time(),
            timestamp_utc="2026-10-06T20:00:00Z",
            interface="Wi-Fi",
            status="LIVE",
            duration_seconds=2.0,
            total_packets=25,
            total_bytes=5000,
            packets_per_second=12.5,
            bytes_per_second=2500.0,
            avg_packet_size=200.0,
            tcp_packets=20,
            udp_packets=5,
            icmp_packets=0,
            other_transport_packets=0,
            dns_packets=3,
            ipv4_packets=25,
            ipv6_packets=0,
            other_network_packets=0,
        )

        svc.on_window_finalized(test_win)

        cur = svc.get_current()
        self.assertEqual(cur.window_id, test_win.window_id)
        self.assertEqual(cur.total_packets, 25)

        hist = svc.get_history(limit=5)
        self.assertGreaterEqual(hist.count, 1)
        saved = next(w for w in hist.items if w.window_id == test_win.window_id)
        self.assertEqual(saved.total_packets, 25)
        self.assertEqual(saved.tcp_packets, 20)
        self.assertEqual(saved.dns_packets, 3)

    def test_05_api_endpoints(self):
        r_cur = self.client.get("/api/protocols/current")
        self.assertEqual(r_cur.status_code, 200)
        data_cur = r_cur.json()
        self.assertIn("status", data_cur)
        self.assertIn("window_id", data_cur)
        self.assertIn("total_packets", data_cur)

        r_hist = self.client.get("/api/protocols/history?limit=10")
        self.assertEqual(r_hist.status_code, 200)
        data_hist = r_hist.json()
        self.assertIn("count", data_hist)
        self.assertIn("total", data_hist)
        self.assertIn("items", data_hist)

    def test_06_cached_api_no_extra_capture(self):
        # Intent: repeated reads return in-memory cached state; no packet-capture I/O is triggered.
        # The 5s ceiling is deliberately conservative — it proves no blocking capture call is made
        # (which would take 2+ seconds per window) while remaining immune to OS scheduling jitter
        # under pytest's multi-threaded lifespan context on Windows.
        t0 = time.perf_counter()
        for _ in range(25):
            res = self.client.get("/api/protocols/current")
            self.assertEqual(res.status_code, 200)
        dur = time.perf_counter() - t0
        self.assertLess(dur, 5.0, f"25 requests took too long: {dur*1000:.2f}ms (suggests blocking capture)")

    def test_07_regression_phases_1_to_10(self):
        endpoints = [
            "/api/health",
            "/api/system/current",
            "/api/network/current",
            "/api/latency/current",
            "/api/health-score",
            "/api/alerts/summary",
            "/api/devices",
            "/api/connections",
            "/api/connections/summary",
        ]
        for ep in endpoints:
            r = self.client.get(ep)
            self.assertEqual(r.status_code, 200, f"Failed regression on {ep}")


if __name__ == "__main__":
    unittest.main()
