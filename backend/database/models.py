"""SQLAlchemy Models for System, Network, Interface, and Latency Telemetry Persistence"""
from sqlalchemy import (
    Column, 
    Integer, 
    Float, 
    String, 
    Boolean, 
    Index, 
    UniqueConstraint, 
    Text
)
from backend.database.session import Base

class SystemMetricModel(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(String(36), nullable=False, unique=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    timestamp_utc = Column(String(32), nullable=False)
    
    # Hardware metrics (Nullable if collector degraded)
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    memory_used_bytes = Column(Integer, nullable=True)
    memory_total_bytes = Column(Integer, nullable=True)
    memory_available_bytes = Column(Integer, nullable=True)
    
    disk_percent = Column(Float, nullable=True)
    disk_used_bytes = Column(Integer, nullable=True)
    disk_total_bytes = Column(Integer, nullable=True)
    disk_free_bytes = Column(Integer, nullable=True)
    disk_mount_point = Column(String(64), nullable=True)
    
    uptime_seconds = Column(Float, nullable=True)
    collector_status = Column(String(20), nullable=False, default="OK")
    unavailable_fields = Column(Text, nullable=True)  # JSON-encoded string if any

    __table_args__ = (
        Index("ix_system_metrics_ts", "timestamp"),
    )

class NetworkMetricModel(Base):
    __tablename__ = "network_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(String(36), nullable=False, unique=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    timestamp_utc = Column(String(32), nullable=False)
    
    status = Column(String(20), nullable=False, default="LIVE")  # LIVE, WARMING_UP, RESET
    download_mbps = Column(Float, nullable=True)  # Null if WARMING_UP or RESET
    upload_mbps = Column(Float, nullable=True)    # Null if WARMING_UP or RESET
    
    bytes_recv = Column(Integer, nullable=False)
    bytes_sent = Column(Integer, nullable=False)
    packets_recv = Column(Integer, nullable=False)
    packets_sent = Column(Integer, nullable=False)
    
    elapsed_seconds = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_network_metrics_ts", "timestamp"),
    )

class InterfaceMetricModel(Base):
    __tablename__ = "interface_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(String(36), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    timestamp_utc = Column(String(32), nullable=False)
    
    interface_name = Column(String(64), nullable=False, index=True)
    is_up = Column(Boolean, nullable=False, default=False)
    
    download_mbps = Column(Float, nullable=True)  # Null if WARMING_UP or RESET
    upload_mbps = Column(Float, nullable=True)    # Null if WARMING_UP or RESET
    
    bytes_recv = Column(Integer, nullable=False)
    bytes_sent = Column(Integer, nullable=False)
    packets_recv = Column(Integer, nullable=False)
    packets_sent = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("sample_id", "interface_name", name="uq_sample_interface"),
        Index("ix_iface_metrics_name_ts", "interface_name", "timestamp"),
    )

class LatencyMetricModel(Base):
    """Stores genuine network probe results.
    Each probe runs independently of host sampling, uniquely identified by probe_id,
    and persisted exactly once.
    """
    __tablename__ = "latency_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    probe_id = Column(String(36), nullable=False, unique=True, index=True)
    sample_id = Column(String(36), nullable=True, index=True)  # Associated host sample_id if linked
    timestamp = Column(Float, nullable=False, index=True)
    timestamp_utc = Column(String(32), nullable=False)
    
    target = Column(String(128), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="UNREACHABLE")  # LIVE, PARTIAL, UNREACHABLE, ERROR
    is_reachable = Column(Boolean, nullable=False, default=False)
    
    packets_sent = Column(Integer, nullable=False, default=0)
    packets_received = Column(Integer, nullable=False, default=0)
    packet_loss_percent = Column(Float, nullable=True)
    
    latency_last_ms = Column(Float, nullable=True)
    latency_min_ms = Column(Float, nullable=True)
    latency_max_ms = Column(Float, nullable=True)
    latency_avg_ms = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_latency_metrics_target_ts", "target", "timestamp"),
    )

class AlertModel(Base):
    """Deterministic alert model (Phase 8).
    Tracks alert lifecycle (OPEN, ACKNOWLEDGED, RESOLVED), severity (INFO, WARNING, CRITICAL),
    and consecutive occurrences without inserting duplicates for active conditions.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(36), nullable=False, unique=True, index=True)
    type = Column(String(64), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # INFO, WARNING, CRITICAL
    status = Column(String(20), nullable=False, index=True, default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED
    source = Column(String(64), nullable=False, index=True, default="host")
    message = Column(Text, nullable=False)
    metric_name = Column(String(64), nullable=False)
    observed_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    
    opened_at = Column(Float, nullable=False, index=True)
    opened_at_utc = Column(String(32), nullable=False)
    acknowledged_at = Column(Float, nullable=True)
    acknowledged_at_utc = Column(String(32), nullable=True)
    resolved_at = Column(Float, nullable=True)
    resolved_at_utc = Column(String(32), nullable=True)
    
    last_seen_at = Column(Float, nullable=False)
    last_seen_at_utc = Column(String(32), nullable=False)
    occurrence_count = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_alerts_status_type_source", "status", "type", "source"),
    )


class DeviceModel(Base):
    """Persistent LAN device record (Phase 9).
    Uses normalized MAC address as the primary stable identity when available.
    Devices are never deleted automatically; they accumulate status over time.
    IP address may change (DHCP); MAC is the canonical key when present.
    """
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Stable identity: normalized MAC (e.g. 'aa:bb:cc:dd:ee:ff') or None if unavailable
    mac_address = Column(String(17), nullable=True, index=True)
    # Current known IP (may drift on DHCP)
    ip_address = Column(String(45), nullable=False, index=True)
    # Reverse-DNS hostname if resolvable; null otherwise
    hostname = Column(String(255), nullable=True)
    # Interface where device was observed
    interface_name = Column(String(64), nullable=False)

    # Device lifecycle
    first_seen = Column(Float, nullable=False, index=True)
    first_seen_utc = Column(String(32), nullable=False)
    last_seen = Column(Float, nullable=False, index=True)
    last_seen_utc = Column(String(32), nullable=False)

    # ONLINE / OFFLINE / UNKNOWN
    status = Column(String(16), nullable=False, default="ONLINE", index=True)
    # Incremented each discovery cycle the device is absent; reset to 0 on return
    missed_scan_count = Column(Integer, nullable=False, default=0)

    # Column-level index=True provides: ix_devices_mac, ix_devices_ip, ix_devices_status, etc.


class ProtocolMetricModel(Base):
    """Stores aggregated time-window protocol statistics (Phase 11).
    Never stores individual packets or payload content.
    Only valid LIVE windows record packet metrics; unavailable periods are tracked with status.
    """
    __tablename__ = "protocol_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    window_id = Column(String(36), nullable=False, unique=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    timestamp_utc = Column(String(32), nullable=False)
    interface = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="LIVE", index=True)  # LIVE, WARMING_UP, PERMISSION_REQUIRED, INTERFACE_UNAVAILABLE, ERROR, STOPPED

    window_duration_seconds = Column(Float, nullable=False, default=2.0)
    total_packets = Column(Integer, nullable=False, default=0)
    total_bytes = Column(Integer, nullable=False, default=0)
    packets_per_second = Column(Float, nullable=False, default=0.0)
    bytes_per_second = Column(Float, nullable=False, default=0.0)
    avg_packet_size = Column(Float, nullable=False, default=0.0)

    # Transport classification (TCP + UDP + ICMP + other_transport == total_packets)
    tcp_packets = Column(Integer, nullable=False, default=0)
    udp_packets = Column(Integer, nullable=False, default=0)
    icmp_packets = Column(Integer, nullable=False, default=0)
    other_transport_packets = Column(Integer, nullable=False, default=0)

    # Application subset metadata
    dns_packets = Column(Integer, nullable=False, default=0)

    # Network layer breakdown (ipv4 + ipv6 + other_ip <= total_packets)
    ipv4_packets = Column(Integer, nullable=False, default=0)
    ipv6_packets = Column(Integer, nullable=False, default=0)
    other_network_packets = Column(Integer, nullable=False, default=0)
    # Link-layer non-IP frames (ARP, LLDP, VLAN, 802.1x, etc.)
    non_ip_packets = Column(Integer, nullable=False, default=0)

    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_protocol_metrics_iface_ts", "interface", "timestamp"),
    )
