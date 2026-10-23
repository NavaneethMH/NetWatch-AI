"""Real-time Network Throughput Collector (Phase 3 & 4)
Calculates upload/download Mbps using byte-counter deltas over elapsed monotonic time.
Obtains one pernic=True network snapshot and derives both per-interface and aggregate counters.
"""
import psutil
import time
import threading
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timezone
from backend.schemas.network import (
    NetworkThroughputResponse,
    InterfaceThroughput
)

def get_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class NetworkCollector:
    """Calculates genuine real-time network throughput (Mbps) from psutil byte counters.
    Obtains one single pernic=True snapshot to derive both aggregate and per-interface counters.
    """

    def __init__(self, sample_interval: float = 1.0):
        self._lock = threading.Lock()
        self.sample_interval = sample_interval

        # Global aggregate state derived from sum of interfaces
        self._prev_aggregate_bytes_recv: Optional[int] = None
        self._prev_aggregate_bytes_sent: Optional[int] = None
        self._prev_aggregate_mono: Optional[float] = None

        # Per-interface state: {iface_name: (bytes_recv, bytes_sent, mono_time)}
        self._prev_iface_counters: Dict[str, Tuple[int, int, float]] = {}

        # Cached computed rates
        self._download_mbps: Optional[float] = None
        self._upload_mbps: Optional[float] = None
        self._last_elapsed: Optional[float] = None
        self._is_ready: bool = False
        self._last_status: str = "WARMING_UP"

        # Current cumulative values
        self._bytes_recv_total: int = 0
        self._bytes_sent_total: int = 0
        self._packets_recv_total: int = 0
        self._packets_sent_total: int = 0

        # Per-interface throughput list
        self._interfaces_throughput: List[InterfaceThroughput] = []

        # Background sampling thread
        self._sampler_thread = threading.Thread(target=self._background_sampler, daemon=True)
        self._sampler_thread.start()

    def _sample_once(self):
        """Samples one single pernic=True snapshot and derives aggregate and per-interface Mbps."""
        now_mono = time.monotonic()

        # 1. Obtain single pernic=True snapshot
        try:
            per_nic = psutil.net_io_counters(pernic=True)
            nic_stats = psutil.net_if_stats()
        except Exception:
            return

        if not per_nic:
            return

        # 2. Derive aggregate sums directly from pernic=True for absolute consistency
        current_bytes_recv = sum(c.bytes_recv for c in per_nic.values())
        current_bytes_sent = sum(c.bytes_sent for c in per_nic.values())
        current_pkts_recv = sum(c.packets_recv for c in per_nic.values())
        current_pkts_sent = sum(c.packets_sent for c in per_nic.values())

        with self._lock:
            self._bytes_recv_total = current_bytes_recv
            self._bytes_sent_total = current_bytes_sent
            self._packets_recv_total = current_pkts_recv
            self._packets_sent_total = current_pkts_sent

            # Compute aggregate throughput if previous snapshot exists
            if self._prev_aggregate_mono is not None and self._prev_aggregate_bytes_recv is not None:
                elapsed = now_mono - self._prev_aggregate_mono
                if elapsed > 0.05:
                    delta_recv = current_bytes_recv - self._prev_aggregate_bytes_recv
                    delta_sent = current_bytes_sent - self._prev_aggregate_bytes_sent

                    # Check for counter reset / adapter reconnect
                    if delta_recv < 0 or delta_sent < 0:
                        self._download_mbps = None
                        self._upload_mbps = None
                        self._last_status = "RESET"
                        self._is_ready = False
                    else:
                        self._download_mbps = round(((delta_recv * 8) / elapsed) / 1_000_000.0, 3)
                        self._upload_mbps = round(((delta_sent * 8) / elapsed) / 1_000_000.0, 3)
                        self._last_elapsed = round(elapsed, 2)
                        self._is_ready = True
                        self._last_status = "LIVE"
            else:
                self._is_ready = False
                self._last_status = "WARMING_UP"

            self._prev_aggregate_bytes_recv = current_bytes_recv
            self._prev_aggregate_bytes_sent = current_bytes_sent
            self._prev_aggregate_mono = now_mono

            # Compute per-interface throughput
            iface_list: List[InterfaceThroughput] = []
            for iface_name, nic_io in per_nic.items():
                is_up = nic_stats[iface_name].isup if iface_name in nic_stats else False
                if_dl: Optional[float] = None
                if_ul: Optional[float] = None

                if iface_name in self._prev_iface_counters:
                    prev_r, prev_s, prev_t = self._prev_iface_counters[iface_name]
                    if_elapsed = now_mono - prev_t
                    if if_elapsed > 0.05:
                        d_r = nic_io.bytes_recv - prev_r
                        d_s = nic_io.bytes_sent - prev_s
                        if d_r < 0 or d_s < 0:
                            if_dl = None
                            if_ul = None
                        else:
                            if_dl = round(((d_r * 8) / if_elapsed) / 1_000_000.0, 3)
                            if_ul = round(((d_s * 8) / if_elapsed) / 1_000_000.0, 3)

                self._prev_iface_counters[iface_name] = (nic_io.bytes_recv, nic_io.bytes_sent, now_mono)

                iface_list.append(
                    InterfaceThroughput(
                        name=iface_name,
                        is_up=is_up,
                        download_mbps=if_dl,
                        upload_mbps=if_ul,
                        bytes_recv=nic_io.bytes_recv,
                        bytes_sent=nic_io.bytes_sent,
                        packets_recv=nic_io.packets_recv,
                        packets_sent=nic_io.packets_sent
                    )
                )

            self._interfaces_throughput = iface_list

    def _background_sampler(self):
        """Continuous background thread sampling counters at fixed intervals."""
        self._sample_once()
        while True:
            time.sleep(self.sample_interval)
            try:
                self._sample_once()
            except Exception:
                pass

    def collect(self) -> NetworkThroughputResponse:
        with self._lock:
            return NetworkThroughputResponse(
                timestamp=time.time(),
                timestamp_iso=get_utc_iso(),
                status=self._last_status,
                download_mbps=self._download_mbps if self._is_ready else None,
                upload_mbps=self._upload_mbps if self._is_ready else None,
                bytes_recv_total=self._bytes_recv_total,
                bytes_sent_total=self._bytes_sent_total,
                packets_recv_total=self._packets_recv_total,
                packets_sent_total=self._packets_sent_total,
                sample_interval_seconds=self._last_elapsed,
                interfaces=list(self._interfaces_throughput)
            )

# Global singleton network throughput collector
network_collector = NetworkCollector(sample_interval=1.0)
