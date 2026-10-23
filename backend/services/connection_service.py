# -*- coding: utf-8 -*-
"""Active Connection Service (Phase 10).

Maintains current in-memory connection state:
- Tracks first_observed, last_observed for active connections.
- Automatically handles appearing and disappearing connections between scans.
- Provides thread-safe read access for REST APIs and WebSocket summary broadcasts.
- API queries never trigger OS connection scans.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.collectors.connections import RawConnectionEntry, connection_collector
from backend.schemas.connection import ConnectionItem, ConnectionListResponse, ConnectionSummary

logger = logging.getLogger("netwatch.services.connections")


class ConnectionService:
    """Service managing live active network connections in memory."""

    def __init__(self, register_with_collector: bool = True):
        self._lock = threading.RLock()
        # runtime_key -> ConnectionItem
        self._active_connections: Dict[str, ConnectionItem] = {}
        self._summary = ConnectionSummary()
        self._last_scan_ts: float = 0.0

        # Register callback to receive scan batches from the collector
        if register_with_collector:
            connection_collector.register_callback(self.update_connections)

    def update_connections(
        self,
        raw_entries: List[RawConnectionEntry],
        scan_timestamp: float,
        duration_ms: float,
    ) -> None:
        """Callback invoked by ConnectionCollector on completion of each scan cycle."""
        iso_str = datetime.fromtimestamp(scan_timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._lock:
            self._last_scan_ts = scan_timestamp
            new_active_map: Dict[str, ConnectionItem] = {}

            tcp_count = 0
            udp_count = 0
            est_count = 0
            listen_count = 0
            tw_count = 0
            cw_count = 0
            other_count = 0

            for entry in raw_entries:
                key = entry.runtime_key
                # State counts
                st_upper = (entry.state or "").upper()
                if entry.protocol == "TCP":
                    tcp_count += 1
                elif entry.protocol == "UDP":
                    udp_count += 1

                if st_upper == "ESTABLISHED":
                    est_count += 1
                elif st_upper == "LISTEN":
                    listen_count += 1
                elif st_upper == "TIME_WAIT":
                    tw_count += 1
                elif st_upper == "CLOSE_WAIT":
                    cw_count += 1
                else:
                    other_count += 1

                # If existing connection, preserve first_observed
                existing = self._active_connections.get(key)
                if existing:
                    first_ts = existing.first_observed
                    first_iso = existing.first_observed_utc
                else:
                    first_ts = scan_timestamp
                    first_iso = iso_str

                item = ConnectionItem(
                    id=key,
                    protocol=entry.protocol,
                    family=entry.family,
                    local_ip=entry.local_ip,
                    local_port=entry.local_port,
                    remote_ip=entry.remote_ip,
                    remote_port=entry.remote_port,
                    state=entry.state,
                    pid=entry.pid,
                    process_name=entry.process_name,
                    first_observed=first_ts,
                    first_observed_utc=first_iso,
                    last_observed=scan_timestamp,
                    last_observed_utc=iso_str,
                )
                new_active_map[key] = item

            # Overwrite active connections: connections no longer present naturally disappear
            self._active_connections = new_active_map

            # Update summary
            self._summary = ConnectionSummary(
                total=len(new_active_map),
                tcp=tcp_count,
                udp=udp_count,
                established=est_count,
                listening=listen_count,
                time_wait=tw_count,
                close_wait=cw_count,
                other=other_count,
                last_scan_utc=iso_str,
                scan_duration_ms=round(duration_ms, 2),
            )

    def get_connections(
        self,
        protocol: Optional[str] = None,
        state: Optional[str] = None,
        process: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> ConnectionListResponse:
        """Query active connections from in-memory cache.
        Does NOT trigger an OS scan.
        """
        with self._lock:
            items = list(self._active_connections.values())

        # Filtering
        if protocol:
            p_upper = protocol.upper()
            items = [c for c in items if c.protocol.upper() == p_upper]

        if state:
            s_upper = state.upper()
            items = [c for c in items if c.state.upper() == s_upper]

        if process:
            proc_lower = process.lower()
            items = [
                c for c in items
                if c.process_name and proc_lower in c.process_name.lower()
            ]

        if search:
            q = search.lower()
            filtered = []
            for c in items:
                match = (
                    (c.local_ip and q in c.local_ip.lower())
                    or (c.remote_ip and q in c.remote_ip.lower())
                    or (c.local_port and q in str(c.local_port))
                    or (c.remote_port and q in str(c.remote_port))
                    or (c.process_name and q in c.process_name.lower())
                    or (c.pid is not None and q in str(c.pid))
                    or (c.state and q in c.state.lower())
                )
                if match:
                    filtered.append(c)
            items = filtered

        total = len(items)
        # Sort by state (ESTABLISHED first, then LISTEN, etc.) and then process_name
        def sort_key(c: ConnectionItem):
            st = c.state.upper()
            priority = 0 if st == "ESTABLISHED" else (1 if st == "LISTEN" else 2)
            return (priority, c.process_name or "zzz", c.local_port or 0)

        items.sort(key=sort_key)
        paged_items = items[:limit]

        return ConnectionListResponse(
            count=len(paged_items),
            total=total,
            items=paged_items,
        )

    def get_summary(self) -> ConnectionSummary:
        """Return the current lightweight connection summary."""
        with self._lock:
            return self._summary


# Global singleton instance
connection_service = ConnectionService()
