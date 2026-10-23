# -*- coding: utf-8 -*-
"""Real Packet & Protocol Collector (Phase 11).

Captures packet-level metadata from the active host network interface.
Never stores packet payloads, browser contents, or credentials.
Extracts only protocol headers and packet lengths.
Strictly aggregates packets into discrete time windows (default: 2.0 seconds).
If Npcap / raw socket permissions are missing, enters PERMISSION_REQUIRED honestly
without fabricating fake traffic or crashing the application.
"""
from __future__ import annotations

import logging
import os
import socket
import struct
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import psutil

from backend.core.config import settings

logger = logging.getLogger("netwatch.collectors.packets")


@dataclass
class PacketMetadata:
    """Lightweight extracted metadata for a single packet."""
    size: int
    family: str       # IPv4, IPv6, OTHER
    transport: str    # TCP, UDP, ICMP, OTHER
    is_dns: bool      # port 53
    non_ip: bool = False  # True when frame is non-IP (ARP, LLDP, VLAN, etc.)


@dataclass
class WindowAggregate:
    """Aggregated counters for a discrete collection window."""
    window_id: str
    timestamp: float
    timestamp_utc: str
    interface: Optional[str]
    status: str
    duration_seconds: float = 2.0

    total_packets: int = 0
    total_bytes: int = 0
    packets_per_second: float = 0.0
    bytes_per_second: float = 0.0
    avg_packet_size: float = 0.0

    tcp_packets: int = 0
    udp_packets: int = 0
    icmp_packets: int = 0
    other_transport_packets: int = 0  # IP frames with unrecognised transport (SCTP, GRE, …)

    dns_packets: int = 0

    ipv4_packets: int = 0
    ipv6_packets: int = 0
    other_network_packets: int = 0    # IP frames with unrecognised network variant
    non_ip_packets: int = 0           # Link-layer frames: ARP, LLDP, VLAN, 802.1x, …

    error_message: Optional[str] = None


def parse_raw_ip_packet(raw: bytes) -> PacketMetadata:
    """Zero-copy fast binary header decoder.
    Extracts transport protocol, IP family, port 53 DNS indicator, and size.
    Never retains or inspects packet payload contents.
    """
    size = len(raw)
    if size < 20:
        return PacketMetadata(size=size, family="OTHER", transport="OTHER", is_dns=False)

    version = (raw[0] >> 4)
    if version == 4:
        family = "IPv4"
        ihl = (raw[0] & 0x0F) * 4
        if size < ihl:
            return PacketMetadata(size=size, family="IPv4", transport="OTHER", is_dns=False)
        proto = raw[9]
        payload = raw[ihl:]
    elif version == 6:
        family = "IPv6"
        if size < 40:
            return PacketMetadata(size=size, family="IPv6", transport="OTHER", is_dns=False)
        proto = raw[6]
        payload = raw[40:]
    else:
        return PacketMetadata(size=size, family="OTHER", transport="OTHER", is_dns=False)

    transport = "OTHER"
    is_dns = False

    if proto == 6:  # TCP
        transport = "TCP"
        if len(payload) >= 4:
            sport = (payload[0] << 8) | payload[1]
            dport = (payload[2] << 8) | payload[3]
            if sport == 53 or dport == 53:
                is_dns = True
    elif proto == 17:  # UDP
        transport = "UDP"
        if len(payload) >= 4:
            sport = (payload[0] << 8) | payload[1]
            dport = (payload[2] << 8) | payload[3]
            if sport == 53 or dport == 53:
                is_dns = True
    elif proto in (1, 58):  # ICMP or ICMPv6
        transport = "ICMP"

    return PacketMetadata(
        size=size,
        family=family,
        transport=transport,
        is_dns=is_dns,
    )


class PacketCollector:
    """Dedicated background packet collector with bounded aggregation windows."""

    def __init__(self, window_seconds: float = 2.0):
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[WindowAggregate], None]] = None

        self.current_interface: Optional[str] = None
        self.current_ip: Optional[str] = None
        self.status: str = "WARMING_UP"
        self.limitation_reason: Optional[str] = None

        # Bounded in-flight window counters (reset every window_seconds)
        self._window_lock = threading.Lock()
        self._window_start: float = time.time()
        self._reset_window_counters()

    def _reset_window_counters(self) -> None:
        self._total_pkts = 0
        self._total_bytes = 0
        self._tcp_pkts = 0
        self._udp_pkts = 0
        self._icmp_pkts = 0
        self._other_transport = 0
        self._dns_pkts = 0
        self._ipv4_pkts = 0
        self._ipv6_pkts = 0
        self._other_net = 0
        self._non_ip_pkts = 0

    def register_callback(self, cb: Callable[[WindowAggregate], None]) -> None:
        """Register callback for finalized window summaries.
        Signature: cb(window_aggregate)
        """
        self._callback = cb

    def record_packet(self, meta: PacketMetadata) -> None:
        """Feed a single packet metadata entry into the current window accumulator.
        Lock is held only for arithmetic increment; zero heap retention.

        Invariants (when LIVE):
          non_ip + (tcp + udp + icmp + other_transport) == total_packets
          ipv4 + ipv6 + other_network == total_packets - non_ip  (i.e. IP packets only)
        """
        with self._window_lock:
            self._total_pkts += 1
            self._total_bytes += meta.size

            if meta.non_ip:
                # Link-layer frame (ARP, LLDP, VLAN, …) — not an IP packet.
                self._non_ip_pkts += 1
                # non_ip frames have no transport or network-layer classification.
                return

            # IP packet path
            if meta.transport == "TCP":
                self._tcp_pkts += 1
            elif meta.transport == "UDP":
                self._udp_pkts += 1
            elif meta.transport == "ICMP":
                self._icmp_pkts += 1
            else:
                self._other_transport += 1  # SCTP, GRE, IGMP, ESP, …

            if meta.is_dns:
                self._dns_pkts += 1

            if meta.family == "IPv4":
                self._ipv4_pkts += 1
            elif meta.family == "IPv6":
                self._ipv6_pkts += 1
            else:
                self._other_net += 1

    def finalize_current_window(self) -> WindowAggregate:
        """Flushes the current window counters and creates a WindowAggregate."""
        now = time.time()
        iso = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._window_lock:
            dur = max(0.001, now - self._window_start)
            self._window_start = now

            tot_p = self._total_pkts
            tot_b = self._total_bytes
            tcp = self._tcp_pkts
            udp = self._udp_pkts
            icmp = self._icmp_pkts
            oth_t = self._other_transport
            dns = self._dns_pkts
            ipv4 = self._ipv4_pkts
            ipv6 = self._ipv6_pkts
            oth_n = self._other_net
            non_ip = self._non_ip_pkts

            self._reset_window_counters()

        pps = round(tot_p / dur, 2)
        bps = round(tot_b / dur, 2)
        avg_sz = round(tot_b / tot_p, 2) if tot_p > 0 else 0.0

        return WindowAggregate(
            window_id=str(uuid.uuid4()),
            timestamp=now,
            timestamp_utc=iso,
            interface=self.current_interface,
            status=self.status,
            duration_seconds=round(max(0.01, dur), 2),
            total_packets=tot_p,
            total_bytes=tot_b,
            packets_per_second=pps,
            bytes_per_second=bps,
            avg_packet_size=avg_sz,
            tcp_packets=tcp,
            udp_packets=udp,
            icmp_packets=icmp,
            other_transport_packets=oth_t,
            dns_packets=dns,
            ipv4_packets=ipv4,
            ipv6_packets=ipv6,
            other_network_packets=oth_n,
            non_ip_packets=non_ip,
            error_message=self.limitation_reason,
        )

    def _detect_active_interface(self) -> Tuple[Optional[str], Optional[str]]:
        """Finds the primary connected network interface."""
        try:
            from backend.collectors.device_discovery import _select_lan_interface
            res = _select_lan_interface()
            if res:
                return res[0], res[1]
        except Exception:
            pass

        # Fallback via psutil
        for iface, addrs in psutil.net_if_addrs().items():
            if "virtual" in iface.lower() or "host-only" in iface.lower() or "loopback" in iface.lower():
                continue
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith("127.") and not a.address.startswith("169.254."):
                    return iface, a.address
        return None, None

    def start(self) -> None:
        """Start the packet collector background worker."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_collector_loop,
                daemon=True,
                name="PacketCollector",
            )
            self._thread.start()
            logger.info("PacketCollector background thread started.")

    def stop(self) -> None:
        """Stop the packet collector cleanly."""
        with self._lock:
            if not self._is_running:
                return
            self._stop_event.set()
            self._is_running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.status = "STOPPED"
        logger.info("PacketCollector stopped.")

    def _run_collector_loop(self) -> None:
        """Lifecycle loop: manages capture attempt, window timers, and graceful degradation."""
        while not self._stop_event.is_set():
            iface_name, host_ip = self._detect_active_interface()
            self.current_interface = iface_name
            self.current_ip = host_ip

            if not iface_name or not host_ip:
                self.status = "INTERFACE_UNAVAILABLE"
                self.limitation_reason = "No active network interface with IP address found."
                self._emit_idle_window()
                self._stop_event.wait(timeout=self.window_seconds)
                continue

            # 1. Attempt raw socket (Windows Administrator)
            raw_sock = self._try_open_raw_socket(host_ip)
            if raw_sock is not None:
                self.status = "LIVE"
                self.limitation_reason = None
                self._run_live_capture(raw_sock)
                continue

            # 2. Attempt Scapy/Npcap L2 socket (Standard User or Administrator with Npcap)
            pcap_sock = self._try_open_pcap_socket(iface_name, host_ip)
            if pcap_sock is not None:
                self.status = "LIVE"
                self.limitation_reason = None
                self._run_pcap_capture(pcap_sock)
                continue

            # 3. Capture permission or driver unavailable
            self.status = "PERMISSION_REQUIRED"
            self.limitation_reason = (
                "Packet capture requires Npcap or Administrator privileges on Windows. "
                "All other NetWatch monitoring features remain fully functional."
            )
            self._emit_idle_window()
            self._stop_event.wait(timeout=self.window_seconds)

    def _try_open_raw_socket(self, host_ip: str) -> Optional[socket.socket]:
        """Attempts to open native Windows raw socket with SIO_RCVALL."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
            s.bind((host_ip, 0))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            # SIO_RCVALL = 0x98000001
            s.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
            s.settimeout(0.5)
            return s
        except (PermissionError, OSError) as e:
            logger.debug(f"Raw socket open declined: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error opening raw socket: {e}")
            return None

    def _try_open_pcap_socket(self, iface_name: str, host_ip: str):
        """Attempts to open Npcap/Scapy L2 listen socket."""
        try:
            import scapy.all as scapy
            if not getattr(scapy.conf, "use_pcap", False):
                return None

            # Map friendly name or host IP to Scapy interface
            target_iface = None
            for k, iface in scapy.conf.ifaces.items():
                if getattr(iface, "ip", None) == host_ip:
                    target_iface = iface
                    break
                if getattr(iface, "name", None) == iface_name:
                    target_iface = iface

            if target_iface is None:
                target_iface = iface_name

            s = scapy.conf.L2listen(iface=target_iface)
            if hasattr(s, "pcap_fd") and hasattr(s.pcap_fd, "setnonblock"):
                s.pcap_fd.setnonblock(True)
            return s
        except Exception as e:
            logger.debug(f"Npcap L2 socket open declined: {e}")
            return None

    @staticmethod
    def _decode_ethernet_frame(data: bytes) -> PacketMetadata:
        """Classify an Ethernet II frame.

        Returns a PacketMetadata with non_ip=True for non-IP EtherTypes
        (ARP=0x0806, LLDP=0x88CC, VLAN=0x8100, 802.1x=0x888E, etc.).
        Strips the 14-byte Ethernet header before passing to parse_raw_ip_packet
        for IPv4 (0x0800) and IPv6 (0x86DD) frames.
        Treats short or raw-IP data (no Ethernet header) gracefully.
        """
        if len(data) >= 14:
            ethertype = (data[12] << 8) | data[13]
            if ethertype == 0x0800:          # IPv4
                return parse_raw_ip_packet(data[14:])
            elif ethertype == 0x86DD:         # IPv6
                return parse_raw_ip_packet(data[14:])
            else:
                # Non-IP link-layer frame (ARP, LLDP, VLAN, 802.1x, …)
                return PacketMetadata(
                    size=len(data),
                    family="OTHER",
                    transport="OTHER",
                    is_dns=False,
                    non_ip=True,
                )
        # Short frame or raw-IP socket data (no Ethernet header)
        return parse_raw_ip_packet(data)

    def _run_pcap_capture(self, pcap_sock) -> None:
        """Reads packets from Npcap/Scapy L2 socket non-blockingly."""
        logger.info(f"Packet capture LIVE via Npcap on {self.current_interface} ({self.current_ip}).")
        last_emit = time.time()

        try:
            while not self._stop_event.is_set():
                had_data = False
                try:
                    if hasattr(pcap_sock, "pcap_fd") and hasattr(pcap_sock.pcap_fd, "next"):
                        hdr, data = pcap_sock.pcap_fd.next()
                        if data:
                            had_data = True
                            meta = self._decode_ethernet_frame(bytes(data))
                            self.record_packet(meta)
                    else:
                        # Fallback to recv_raw
                        pkt_type, pkt_data, pkt_time = pcap_sock.recv_raw(65535)
                        if pkt_data:
                            had_data = True
                            meta = self._decode_ethernet_frame(bytes(pkt_data))
                            self.record_packet(meta)
                except Exception as ex:
                    logger.debug(f"Pcap packet recv exception: {ex}")
                    had_data = False

                if not had_data:
                    # Sleep slightly to avoid pegging CPU when idle
                    time.sleep(0.005)

                now = time.time()
                if now - last_emit >= self.window_seconds:
                    win = self.finalize_current_window()
                    if self._callback:
                        self._callback(win)
                    last_emit = now

        finally:
            try:
                pcap_sock.close()
            except Exception:
                pass

    def _run_live_capture(self, raw_sock: socket.socket) -> None:
        """Reads packets in small time blocks until stopped or error."""
        logger.info(f"Packet capture LIVE on {self.current_interface} ({self.current_ip}).")
        last_emit = time.time()

        try:
            while not self._stop_event.is_set():
                try:
                    data, _ = raw_sock.recvfrom(65535)
                    meta = parse_raw_ip_packet(data)
                    self.record_packet(meta)
                except socket.timeout:
                    pass
                except Exception as ex:
                    logger.error(f"Error during raw packet receive: {ex}")
                    break

                now = time.time()
                if now - last_emit >= self.window_seconds:
                    win = self.finalize_current_window()
                    if self._callback:
                        self._callback(win)
                    last_emit = now

        finally:
            try:
                raw_sock.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            except Exception:
                pass
            raw_sock.close()

    def _emit_idle_window(self) -> None:
        """Emits an aggregated window record when capture is not LIVE."""
        win = self.finalize_current_window()
        if self._callback:
            self._callback(win)


# Global singleton collector
packet_collector = PacketCollector()

