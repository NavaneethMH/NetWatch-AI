import sys
sys.path.insert(0, r'c:\Users\navan\OneDrive\Desktop\NetWatch AI')

import unittest
from backend.collectors.packets import PacketCollector, PacketMetadata, parse_raw_ip_packet

class TestProtocolAccountingSuite(unittest.TestCase):
    def test_tcp_accounting(self):
        col = PacketCollector(window_seconds=1.0)
        col.record_packet(PacketMetadata(size=60, family="IPv4", transport="TCP", is_dns=False, non_ip=False))
        col.record_packet(PacketMetadata(size=120, family="IPv6", transport="TCP", is_dns=False, non_ip=False))
        win = col.finalize_current_window()
        self.assertEqual(win.total_packets, 2)
        self.assertEqual(win.tcp_packets, 2)
        self.assertEqual(win.udp_packets, 0)
        self.assertEqual(win.icmp_packets, 0)
        self.assertEqual(win.other_transport_packets, 0)
        self.assertEqual(win.non_ip_packets, 0)
        self.assertEqual(win.dns_packets, 0)
        self.assertEqual(
            win.tcp_packets + win.udp_packets + win.icmp_packets + win.other_transport_packets + win.non_ip_packets,
            win.total_packets
        )

    def test_udp_and_dns_accounting(self):
        col = PacketCollector(window_seconds=1.0)
        # Regular UDP
        col.record_packet(PacketMetadata(size=80, family="IPv4", transport="UDP", is_dns=False, non_ip=False))
        # DNS over UDP
        col.record_packet(PacketMetadata(size=90, family="IPv4", transport="UDP", is_dns=True, non_ip=False))
        # DNS over TCP
        col.record_packet(PacketMetadata(size=110, family="IPv4", transport="TCP", is_dns=True, non_ip=False))
        win = col.finalize_current_window()
        self.assertEqual(win.total_packets, 3)
        self.assertEqual(win.tcp_packets, 1)
        self.assertEqual(win.udp_packets, 2)
        self.assertEqual(win.dns_packets, 2)
        # Invariant: DNS is a subset, not a separate transport category!
        self.assertLessEqual(win.dns_packets, win.tcp_packets + win.udp_packets)
        self.assertEqual(
            win.tcp_packets + win.udp_packets + win.icmp_packets + win.other_transport_packets + win.non_ip_packets,
            win.total_packets
        )

    def test_icmp_and_other_ip_transport(self):
        col = PacketCollector(window_seconds=1.0)
        # ICMP
        col.record_packet(PacketMetadata(size=64, family="IPv4", transport="ICMP", is_dns=False, non_ip=False))
        # Other transport (SCTP, GRE, ESP, IGMP)
        col.record_packet(PacketMetadata(size=100, family="IPv4", transport="OTHER", is_dns=False, non_ip=False))
        win = col.finalize_current_window()
        self.assertEqual(win.total_packets, 2)
        self.assertEqual(win.icmp_packets, 1)
        self.assertEqual(win.other_transport_packets, 1)
        self.assertEqual(win.non_ip_packets, 0)
        self.assertEqual(
            win.tcp_packets + win.udp_packets + win.icmp_packets + win.other_transport_packets + win.non_ip_packets,
            win.total_packets
        )

    def test_layer2_non_ip_frames_arp_and_lldp(self):
        col = PacketCollector(window_seconds=1.0)
        # ARP frame (non_ip=True)
        col.record_packet(PacketMetadata(size=42, family="OTHER", transport="OTHER", is_dns=False, non_ip=True))
        # LLDP frame (non_ip=True)
        col.record_packet(PacketMetadata(size=60, family="OTHER", transport="OTHER", is_dns=False, non_ip=True))
        # 1 TCP IP frame
        col.record_packet(PacketMetadata(size=100, family="IPv4", transport="TCP", is_dns=False, non_ip=False))
        win = col.finalize_current_window()
        self.assertEqual(win.total_packets, 3)
        self.assertEqual(win.tcp_packets, 1)
        self.assertEqual(win.other_transport_packets, 0)  # ARP/LLDP must NOT be added to other_transport!
        self.assertEqual(win.non_ip_packets, 2)
        # Strict invariant verification
        self.assertEqual(
            win.tcp_packets + win.udp_packets + win.icmp_packets + win.other_transport_packets + win.non_ip_packets,
            win.total_packets
        )

    def test_comprehensive_mixed_frame_invariant(self):
        col = PacketCollector(window_seconds=1.0)
        frames = [
            PacketMetadata(size=100, family="IPv4", transport="TCP", is_dns=False, non_ip=False),
            PacketMetadata(size=120, family="IPv6", transport="TCP", is_dns=True, non_ip=False),
            PacketMetadata(size=80, family="IPv4", transport="UDP", is_dns=True, non_ip=False),
            PacketMetadata(size=70, family="IPv6", transport="UDP", is_dns=False, non_ip=False),
            PacketMetadata(size=64, family="IPv4", transport="ICMP", is_dns=False, non_ip=False),
            PacketMetadata(size=90, family="IPv4", transport="OTHER", is_dns=False, non_ip=False), # SCTP/GRE
            PacketMetadata(size=42, family="OTHER", transport="OTHER", is_dns=False, non_ip=True),  # ARP
            PacketMetadata(size=60, family="OTHER", transport="OTHER", is_dns=False, non_ip=True),  # LLDP
        ]
        for f in frames:
            col.record_packet(f)

        win = col.finalize_current_window()
        self.assertEqual(win.total_packets, 8)
        self.assertEqual(win.tcp_packets, 2)
        self.assertEqual(win.udp_packets, 2)
        self.assertEqual(win.icmp_packets, 1)
        self.assertEqual(win.other_transport_packets, 1)
        self.assertEqual(win.non_ip_packets, 2)
        self.assertEqual(win.dns_packets, 2)

        # Invariant 1: Transport + non_ip == total_packets
        self.assertEqual(
            win.tcp_packets + win.udp_packets + win.icmp_packets + win.other_transport_packets + win.non_ip_packets,
            win.total_packets
        )
        # Invariant 2: Network breakdown (IP frames only)
        self.assertEqual(win.ipv4_packets, 4)
        self.assertEqual(win.ipv6_packets, 2)
        self.assertEqual(win.other_network_packets, 0)
        self.assertEqual(win.ipv4_packets + win.ipv6_packets + win.other_network_packets, win.total_packets - win.non_ip_packets)

if __name__ == '__main__':
    unittest.main()
