# -*- coding: utf-8 -*-
"""Real Active Connection Collector (Phase 10).

Monitors this host's genuine network connections using psutil.net_connections().
Does NOT perform remote port scanning, probing, packet capture, or payload inspection.
Gracefully handles psutil.AccessDenied, psutil.NoSuchProcess, unavailable PIDs/process names,
and IPv4/IPv6 connections.
Runs autonomously in a dedicated background worker thread at a configurable cadence.
"""
from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import psutil

from backend.core.config import settings

logger = logging.getLogger("netwatch.collectors.connections")


@dataclass
class RawConnectionEntry:
    protocol: str
    family: str
    local_ip: Optional[str]
    local_port: Optional[int]
    remote_ip: Optional[str]
    remote_port: Optional[int]
    state: str
    pid: Optional[int]
    process_name: Optional[str]
    runtime_key: str


class ConnectionCollector:
    """Dedicated collector for monitoring host active network connections."""

    def __init__(self, interval: Optional[float] = None):
        self.interval = interval if interval is not None else settings.CONNECTION_SCAN_INTERVAL_SECONDS
        self._lock = threading.Lock()
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[List[RawConnectionEntry], float, float], None]] = None

    def register_callback(self, cb: Callable[[List[RawConnectionEntry], float, float], None]) -> None:
        """Register a callback invoked when a connection scan cycle finishes.
        Callback signature: cb(entries, scan_time_timestamp, duration_ms)
        """
        self._callback = cb

    def scan_connections_now(self) -> Tuple[List[RawConnectionEntry], float]:
        """Perform a single synchronous scan of host connections.
        Returns (entries, duration_ms).
        Never raises exceptions out to caller; returns empty list on unexpected failure.
        """
        t0 = time.perf_counter()
        entries: List[RawConnectionEntry] = []

        try:
            raw_conns = psutil.net_connections(kind="inet")
        except psutil.AccessDenied:
            logger.warning("AccessDenied when calling psutil.net_connections(kind='inet').")
            return [], (time.perf_counter() - t0) * 1000.0
        except Exception as e:
            logger.error(f"Error querying psutil.net_connections: {e}")
            return [], (time.perf_counter() - t0) * 1000.0

        # Cache process names across this scan batch to avoid repeated psutil.Process() calls
        pids = {c.pid for c in raw_conns if c.pid is not None}
        proc_names: Dict[int, Optional[str]] = {}
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc_names[pid] = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_names[pid] = None
            except Exception:
                proc_names[pid] = None

        for c in raw_conns:
            # Protocol: TCP vs UDP
            if c.type == socket.SOCK_STREAM:
                proto = "TCP"
            elif c.type == socket.SOCK_DGRAM:
                proto = "UDP"
            else:
                proto = str(c.type)

            # Family: IPv4 vs IPv6
            family = "IPv4" if c.family == socket.AF_INET else ("IPv6" if c.family == socket.AF_INET6 else str(c.family))

            # Local endpoint
            lip: Optional[str] = None
            lport: Optional[int] = None
            if c.laddr:
                lip = c.laddr.ip
                lport = c.laddr.port

            # Remote endpoint
            rip: Optional[str] = None
            rport: Optional[int] = None
            if c.raddr:
                rip = c.raddr.ip
                rport = c.raddr.port

            # State
            state = c.status if c.status else "NONE"

            # PID & process name
            pid = c.pid
            pname = proc_names.get(pid) if pid is not None else None

            # Stable runtime identity key: (protocol, local_ip, local_port, remote_ip, remote_port, pid)
            # Ephemeral ports change when new sockets open, which naturally yields a distinct runtime key.
            runtime_key = f"{proto}:{lip or '*'}:{lport or '*'}-{rip or '*'}:{rport or '*'}:{pid or '0'}"

            entries.append(
                RawConnectionEntry(
                    protocol=proto,
                    family=family,
                    local_ip=lip,
                    local_port=lport,
                    remote_ip=rip,
                    remote_port=rport,
                    state=state,
                    pid=pid,
                    process_name=pname,
                    runtime_key=runtime_key,
                )
            )

        dur_ms = (time.perf_counter() - t0) * 1000.0
        return entries, dur_ms

    def start(self) -> None:
        """Start the background collector thread."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="ConnectionCollector",
            )
            self._thread.start()
            logger.info("ConnectionCollector background worker started.")

    def stop(self) -> None:
        """Signal and stop the background collector thread."""
        with self._lock:
            if not self._is_running:
                return
            self._stop_event.set()
            self._is_running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("ConnectionCollector background worker stopped.")

    def _run_loop(self) -> None:
        """Background sampling loop."""
        # Initial scan immediately upon startup
        self._execute_cycle()

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self.interval):
                break
            self._execute_cycle()

    def _execute_cycle(self) -> None:
        try:
            entries, dur_ms = self.scan_connections_now()
            now_ts = time.time()
            if self._callback:
                self._callback(entries, now_ts, dur_ms)
        except Exception as e:
            logger.error(f"Unexpected error in ConnectionCollector cycle: {e}")


# Global singleton instance
connection_collector = ConnectionCollector()
