"""Real-time Latency and Packet-Loss Collector (Phase 7)
Uses background system ping commands to avoid blocking the event loop.
Maintains genuine probe states (LIVE, PARTIAL, UNREACHABLE, ERROR, WARMING_UP),
calculates actual packet loss % without fake zeros or timeout substitutions,
and persists each unique probe execution exactly once to SQLite.
"""
import os
import re
import uuid
import subprocess
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.core.config import settings
from backend.schemas.latency import LatencySnapshot

logger = logging.getLogger("netwatch.collectors.latency")

class LatencyCollector:
    """Probes connectivity to a configured target continuously in a dedicated background worker."""

    def __init__(self):
        self._lock = threading.Lock()
        self.target = settings.PING_TARGET
        self.interval = settings.PING_INTERVAL_SECONDS
        self.count = settings.PING_COUNT
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_probe = None
        
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._last_snapshot = LatencySnapshot(
            probe_id="warmup",
            target=self.target, 
            is_reachable=False, 
            status="WARMING_UP",
            timestamp=now_ts,
            timestamp_utc=now_iso,
            probe_age_seconds=0.0,
            is_stale=False
        )

    def register_callback(self, cb):
        """Registers a callback to be called with the LatencySnapshot when a probe completes."""
        self._on_probe = cb

    def start(self):
        """Starts the background probe worker thread if not already running."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._background_sampler, daemon=True, name="LatencyCollector")
            self._thread.start()
            logger.info(f"LatencyCollector started for target {self.target} (interval={self.interval}s, count={self.count}).")

    def stop(self, timeout: float = 3.0):
        """Cleanly stops background probe worker on shutdown."""
        self._stop_event.set()
        with self._lock:
            self._is_running = False
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        logger.info("LatencyCollector stopped cleanly.")

    def _background_sampler(self):
        """Continuous background thread sampling latency at fixed 5-second start-to-start intervals."""
        # Initial quick probe with 1 count just to get out of WARMING_UP quickly
        self._sample(quick=True)
        next_tick = time.monotonic() + self.interval

        while not self._stop_event.is_set():
            now_mono = time.monotonic()
            wait_time = next_tick - now_mono
            if wait_time > 0:
                if self._stop_event.wait(timeout=wait_time):
                    break
            else:
                # Probe took longer than interval; schedule next probe from now to avoid busy-loop
                next_tick = time.monotonic()

            next_tick += self.interval

            try:
                self._sample(quick=False)
            except Exception as e:
                logger.error(f"Latency collector error during probe: {e}", exc_info=True)

    def _sample(self, quick=False):
        """Performs a real OS-level ping probe and notifies via callback."""
        count = 1 if quick else self.count
        probe_id = str(uuid.uuid4())
        probe_ts = time.time()
        probe_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if os.name == 'nt':
            cmd = ["ping", "-n", str(count), "-w", "1000", self.target]
        else:
            cmd = ["ping", "-c", str(count), "-W", "1", self.target]

        sent = count
        received = 0
        packet_loss: Optional[float] = None
        min_lat: Optional[float] = None
        max_lat: Optional[float] = None
        avg_lat: Optional[float] = None
        last_lat: Optional[float] = None
        status = "ERROR"
        is_reachable = False

        try:
            # Safe non-shell execution with explicit timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=count * 2.0,
                shell=False
            )
            output = result.stdout

            if os.name == 'nt':
                # Windows ping parsing
                # Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)
                stats_match = re.search(r"Packets:\s*Sent\s*=\s*(\d+),\s*Received\s*=\s*(\d+),\s*Lost\s*=\s*(\d+)", output)
                if stats_match:
                    sent = int(stats_match.group(1))
                    received = int(stats_match.group(2))
                else:
                    loss_match = re.search(r"\((\d+)%\s+loss\)", output)
                    if loss_match:
                        loss_pct = float(loss_match.group(1))
                        received = int(round(sent * (1.0 - (loss_pct / 100.0))))

                times_match = re.search(
                    r"Minimum\s*=\s*(\d+)ms,\s*Maximum\s*=\s*(\d+)ms,\s*Average\s*=\s*(\d+)ms",
                    output
                )
                if times_match:
                    min_lat = float(times_match.group(1))
                    max_lat = float(times_match.group(2))
                    avg_lat = float(times_match.group(3))

                replies = re.findall(r"time[=<](\d+)ms", output)
                if replies:
                    last_lat = float(replies[-1])
                elif avg_lat is not None:
                    last_lat = avg_lat

            else:
                # Unix ping parsing
                # 4 packets transmitted, 4 received, 0% packet loss
                stats_match = re.search(r"(\d+)\s+packets transmitted,\s*(\d+)\s+(?:packets\s+)?received", output)
                if stats_match:
                    sent = int(stats_match.group(1))
                    received = int(stats_match.group(2))
                
                times_match = re.search(r"(?:min/avg/max.*?|round-trip.*?)=\s*([\d.]+)/([\d.]+)/([\d.]+)", output)
                if times_match:
                    min_lat = float(times_match.group(1))
                    avg_lat = float(times_match.group(2))
                    max_lat = float(times_match.group(3))

                replies = re.findall(r"time=([\d.]+)\s*ms", output)
                if replies:
                    last_lat = float(replies[-1])
                elif avg_lat is not None:
                    last_lat = avg_lat

            # Determine genuine packet loss percentage
            if sent > 0:
                packet_loss = round(((sent - received) / sent) * 100.0, 1)

            # Determine genuine status: LIVE, PARTIAL, UNREACHABLE, ERROR
            if sent > 0 and received == sent:
                status = "LIVE"
                is_reachable = True
            elif sent > 0 and received > 0:
                status = "PARTIAL"
                is_reachable = True
            elif sent > 0 and received == 0:
                status = "UNREACHABLE"
                is_reachable = False
                # Do NOT substitute timeout duration as latency
                last_lat, min_lat, max_lat, avg_lat = None, None, None, None
            else:
                status = "ERROR"
                is_reachable = False
                last_lat, min_lat, max_lat, avg_lat = None, None, None, None

        except subprocess.TimeoutExpired:
            status = "UNREACHABLE"
            is_reachable = False
            received = 0
            packet_loss = 100.0
            last_lat, min_lat, max_lat, avg_lat = None, None, None, None
        except Exception as e:
            logger.warning(f"Ping execution failed: {e}")
            status = "ERROR"
            is_reachable = False
            received = 0
            packet_loss = None
            last_lat, min_lat, max_lat, avg_lat = None, None, None, None

        snapshot = LatencySnapshot(
            probe_id=probe_id,
            target=self.target,
            status=status,
            is_reachable=is_reachable,
            packets_sent=sent,
            packets_received=received,
            packet_loss_percent=packet_loss,
            latency_last_ms=last_lat,
            latency_min_ms=min_lat,
            latency_max_ms=max_lat,
            latency_avg_ms=avg_lat,
            timestamp=probe_ts,
            timestamp_utc=probe_iso,
            probe_age_seconds=0.0,
            is_stale=False
        )

        with self._lock:
            self._last_snapshot = snapshot

        # Emit probe result to registered callback
        if self._on_probe:
            try:
                self._on_probe(snapshot)
            except Exception as e:
                logger.error(f"Error in on_probe callback: {e}", exc_info=True)

    def _sample_and_persist(self, quick=False):
        """Backward-compatible test hook alias for _sample."""
        return self._sample(quick=quick)

    def collect(self) -> LatencySnapshot:
        """Returns the latest probe snapshot, computing its exact age and staleness."""
        with self._lock:
            snap = self._last_snapshot

        now = time.time()
        age = max(0.0, round(now - snap.timestamp, 1)) if snap.timestamp > 0 else None
        # Stale if older than 2.5x the configured interval
        stale_threshold = self.interval * 2.5
        is_stale = (age is not None and age > stale_threshold)

        # Return a copy with dynamic age and staleness computed
        data = snap.model_dump()
        data["probe_age_seconds"] = age
        data["is_stale"] = is_stale
        return LatencySnapshot(**data)

# Global singleton latency collector
latency_collector = LatencyCollector()
