# -*- coding: utf-8 -*-
"""Protocol and Packet Analytics Schemas (Phase 11)

Strictly typed models for packet metadata analytics.
Never contains packet payloads, deep inspection data, or domain names.
Two orthogonal dimensions:
1. Transport: TCP + UDP + ICMP + other_transport == total_packets
2. Network: IPv4 + IPv6 + other_network <= total_packets
Application subset:
DNS is a subset count of UDP/TCP port 53.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ProtocolWindowMetric(BaseModel):
    """Aggregated protocol summary for a discrete time window."""
    window_id: str
    timestamp: float
    timestamp_utc: str
    interface: Optional[str] = None
    status: str = Field(..., description="LIVE, WARMING_UP, PERMISSION_REQUIRED, INTERFACE_UNAVAILABLE, ERROR, STOPPED")

    window_duration_seconds: float = 2.0
    total_packets: int = 0
    total_bytes: int = 0
    packets_per_second: float = 0.0
    bytes_per_second: float = 0.0
    avg_packet_size: float = 0.0

    # Transport breakdown (IP packets only; sums to total_packets - non_ip_packets when LIVE)
    tcp_packets: int = 0
    udp_packets: int = 0
    icmp_packets: int = 0
    other_transport_packets: int = 0   # IP frames with unrecognised transport (SCTP, GRE, …)

    # Application subset (subset of TCP/UDP traffic on port 53)
    dns_packets: int = 0

    # Network layer breakdown (IP packets only; sums to total_packets - non_ip_packets when LIVE)
    ipv4_packets: int = 0
    ipv6_packets: int = 0
    other_network_packets: int = 0     # IP frames with unrecognised network header variant

    # Link-layer non-IP frames (ARP, LLDP, VLAN, 802.1x, …)
    non_ip_packets: int = 0

    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class ProtocolHistoryResponse(BaseModel):
    """Historical aggregated protocol time windows."""
    count: int
    total: int
    items: List[ProtocolWindowMetric]


class ProtocolSummary(BaseModel):
    """Lightweight summary of protocol statistics for WebSocket broadcasting and dashboard KPIs."""
    status: str = "PERMISSION_REQUIRED"  # LIVE, WARMING_UP, PERMISSION_REQUIRED, etc.
    interface: Optional[str] = None
    pps: float = 0.0
    bps: float = 0.0
    total_packets: int = 0
    tcp: int = 0
    udp: int = 0
    icmp: int = 0
    dns: int = 0
    other: int = 0          # IP frames with unrecognised transport
    non_ip: int = 0         # ARP, LLDP, VLAN, 802.1x, etc.
    ipv4: int = 0
    ipv6: int = 0
    avg_packet_size: float = 0.0
    last_window_utc: Optional[str] = None
    limitation_reason: Optional[str] = None
