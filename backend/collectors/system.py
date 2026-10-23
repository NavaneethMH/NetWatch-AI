"""Real psutil-based host system and network telemetry collector"""
import psutil
import time
import socket
import os
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.schemas.system import (
    SystemTelemetryResponse,
    CpuMetrics,
    MemoryMetrics,
    DiskMetrics,
    NetworkTotals,
    InterfaceInfo,
    InterfaceAddress
)

def get_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class SystemCollector:
    """Collects genuine host hardware, memory, drive, and network metrics via psutil.
    Maintains CPU sampling state to avoid uninitialized or blocking calls.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cpu_primed = False
        self._last_cpu_percent: Optional[float] = None
        self._last_sample_mono = time.monotonic()
        
        # Prime psutil CPU state immediately on instantiation
        psutil.cpu_percent(interval=None)
        
        # Launch a lightweight daemon background sampler that updates CPU every 1 second
        # so requests get instantaneous, primed CPU values with zero blocking sleep
        self._sampler_thread = threading.Thread(target=self._background_cpu_sampler, daemon=True)
        self._sampler_thread.start()

    def _background_cpu_sampler(self):
        """Samples CPU utilization once per second in background."""
        while True:
            try:
                val = psutil.cpu_percent(interval=1.0)
                with self._lock:
                    self._last_cpu_percent = round(val, 1)
                    self._cpu_primed = True
                    self._last_sample_mono = time.monotonic()
            except Exception:
                time.sleep(1.0)

    def collect(self) -> SystemTelemetryResponse:
        unavailable_fields: List[str] = []

        # 1. CPU Usage: Read pre-sampled non-blocking value
        with self._lock:
            cpu_val = self._last_cpu_percent
            is_ready = self._cpu_primed

        cpu_logical = psutil.cpu_count(logical=True)
        cpu_physical = psutil.cpu_count(logical=False)
        cpu = CpuMetrics(
            usage_percent=cpu_val if is_ready else None,
            is_ready=is_ready,
            core_count_logical=cpu_logical,
            core_count_physical=cpu_physical
        )

        # 2. Memory Usage
        try:
            vm = psutil.virtual_memory()
            memory = MemoryMetrics(
                usage_percent=round(vm.percent, 1),
                total_bytes=vm.total,
                used_bytes=vm.used,
                available_bytes=vm.available
            )
        except Exception as e:
            unavailable_fields.append(f"memory: {str(e)}")
            memory = MemoryMetrics(usage_percent=0.0, total_bytes=0, used_bytes=0, available_bytes=0)

        # 3. Disk Usage (Root OS drive)
        try:
            drive_path = os.getenv("SystemDrive", "C:") + "\\" if os.name == "nt" else "/"
            du = psutil.disk_usage(drive_path)
            disk = DiskMetrics(
                usage_percent=round(du.percent, 1),
                total_bytes=du.total,
                used_bytes=du.used,
                free_bytes=du.free,
                mount_point=drive_path
            )
        except Exception as e:
            unavailable_fields.append(f"disk: {str(e)}")
            disk = DiskMetrics(
                usage_percent=0.0,
                total_bytes=0,
                used_bytes=0,
                free_bytes=0,
                mount_point="N/A"
            )

        # 4. Host Uptime
        boot_time = psutil.boot_time()
        uptime_seconds = max(0.0, round(time.time() - boot_time, 1))

        # 5. Network Cumulative Counters
        try:
            net_io = psutil.net_io_counters(pernic=False)
            if net_io:
                net_totals = NetworkTotals(
                    bytes_sent=net_io.bytes_sent,
                    bytes_recv=net_io.bytes_recv,
                    packets_sent=net_io.packets_sent,
                    packets_recv=net_io.packets_recv,
                    errin=net_io.errin,
                    errout=net_io.errout,
                    dropin=net_io.dropin,
                    dropout=net_io.dropout
                )
            else:
                unavailable_fields.append("network_totals: no net_io_counters returned")
                net_totals = NetworkTotals(bytes_sent=0, bytes_recv=0, packets_sent=0, packets_recv=0)
        except Exception as e:
            unavailable_fields.append(f"network_totals: {str(e)}")
            net_totals = NetworkTotals(bytes_sent=0, bytes_recv=0, packets_sent=0, packets_recv=0)

        # 6. Network Interfaces
        interfaces: List[InterfaceInfo] = []
        try:
            net_addrs = psutil.net_if_addrs()
            net_stats = psutil.net_if_stats()

            for iface_name, addrs in net_addrs.items():
                stat = net_stats.get(iface_name)
                is_up = stat.isup if stat else False
                speed = stat.speed if stat else None
                mtu = stat.mtu if stat else None

                parsed_addrs: List[InterfaceAddress] = []
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        family_name = "IPv4"
                    elif hasattr(socket, "AF_INET6") and addr.family == socket.AF_INET6:
                        family_name = "IPv6"
                    elif hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                        family_name = "MAC"
                    else:
                        family_name = str(addr.family)

                    parsed_addrs.append(
                        InterfaceAddress(
                            family=family_name,
                            address=addr.address,
                            netmask=addr.netmask,
                            broadcast=addr.broadcast
                        )
                    )

                interfaces.append(
                    InterfaceInfo(
                        name=iface_name,
                        is_up=is_up,
                        speed_mbps=speed,
                        mtu=mtu,
                        addresses=parsed_addrs
                    )
                )
        except Exception as e:
            unavailable_fields.append(f"interfaces: {str(e)}")

        return SystemTelemetryResponse(
            timestamp=time.time(),
            timestamp_iso=get_utc_iso(),
            system_uptime_seconds=uptime_seconds,
            boot_time_timestamp=boot_time,
            cpu=cpu,
            memory=memory,
            disk=disk,
            network_totals=net_totals,
            interfaces=interfaces,
            collector_status="OK" if not unavailable_fields else "DEGRADED",
            unavailable_fields=unavailable_fields
        )

# Global singleton collector instance
system_collector = SystemCollector()
