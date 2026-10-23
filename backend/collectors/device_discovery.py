# -*- coding: utf-8 -*-
"""LAN Device Discovery Collector (Phase 9).

Discovery strategy (no Npcap/raw sockets required):
  1. Read OS ARP table  (`arp -a`) — zero-privilege, immediate results.
  2. ICMP ping sweep    — stimulates ARP cache population for hosts that
                          have not recently communicated.
  3. Re-read ARP table  — captures newly populated MAC entries.
  4. Hostname resolution via socket.gethostbyaddr() (best-effort, never blocking).

This collector:
  - Runs in exactly one dedicated background thread.
  - Is independent of the 2-second telemetry worker.
  - Never writes to the database directly — it calls back into DeviceService.
  - Never performs port, vulnerability, or internet scanning.
  - Automatically selects the active LAN interface via the default route.
  - Refuses to auto-scan subnets with more than DEVICE_MAX_AUTO_SCAN_HOSTS hosts.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import psutil

from backend.core.config import settings

logger = logging.getLogger("netwatch.collectors.device")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredDevice:
    ip: str
    mac: Optional[str]        # None when ARP lookup yielded nothing
    hostname: Optional[str]   # None when rDNS fails
    interface: str


@dataclass
class ScanResult:
    devices: List[DiscoveredDevice] = field(default_factory=list)
    method: str = "arp_table+icmp_sweep"
    subnet: Optional[str] = None
    interface: Optional[str] = None
    duration_seconds: float = 0.0
    limitation: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: network interface selection
# ---------------------------------------------------------------------------

# VPN/virtual adapter patterns — excluded from automatic LAN selection
_EXCLUDE_PATTERNS = re.compile(
    r'(virtual|virtualbox|vmware|hyper\-v|loopback|bluetooth|wi-fi direct|pseudo|tun|tap|vpn)',
    re.IGNORECASE
)

def _normalize_mac(raw: str) -> Optional[str]:
    """Normalize MAC to 'aa:bb:cc:dd:ee:ff'. Returns None for broadcast/multicast."""
    cleaned = re.sub(r'[^0-9a-fA-F]', '', raw)
    if len(cleaned) != 12:
        return None
    mac = ':'.join(cleaned[i:i+2] for i in range(0, 12, 2)).lower()
    # Exclude broadcast and multicast MACs
    if mac == 'ff:ff:ff:ff:ff:ff':
        return None
    first_byte = int(mac[:2], 16)
    if first_byte & 0x01:   # multicast bit
        return None
    return mac


def _select_lan_interface() -> Optional[Tuple[str, str, str, str]]:
    """
    Returns (iface_name, local_ip, subnet_cidr, gateway_ip) for the active LAN.
    Uses the interface behind the default IPv4 route.
    Returns None if no suitable interface is found.
    """
    # Step 1: find default-route gateway and its local IP via 'route print'
    gw_ip = None
    gw_local_ip = None
    try:
        if os.name == 'nt':
            r = subprocess.run(['route', 'print', '-4'], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0] == '0.0.0.0' and parts[1] == '0.0.0.0':
                    gw_ip = parts[2]
                    gw_local_ip = parts[3]
                    break
        else:
            r = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True, timeout=5)
            m = re.search(r'via\s+(\S+)\s+dev\s+(\S+)\s+src\s+(\S+)', r.stdout)
            if m:
                gw_ip = m.group(1)
                gw_local_ip = m.group(3)
    except Exception as e:
        logger.debug(f"Route lookup failed: {e}")

    # Step 2: match to a psutil interface
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface_name, addr_list in addrs.items():
        # Skip excluded adapters
        if _EXCLUDE_PATTERNS.search(iface_name):
            continue
        if iface_name in stats and not stats[iface_name].isup:
            continue
        for a in addr_list:
            if a.family != socket.AF_INET:
                continue
            if a.address.startswith('127.') or a.address.startswith('169.254.'):
                continue
            # Prefer the interface whose IP matches the default-route local IP
            if gw_local_ip and a.address != gw_local_ip:
                continue
            try:
                net = ipaddress.IPv4Network(f"{a.address}/{a.netmask}", strict=False)
                return iface_name, a.address, str(net), gw_ip or "unknown"
            except Exception:
                continue

    # Fallback: pick first non-excluded active interface with a private RFC1918 address
    for iface_name, addr_list in addrs.items():
        if _EXCLUDE_PATTERNS.search(iface_name):
            continue
        if iface_name in stats and not stats[iface_name].isup:
            continue
        for a in addr_list:
            if a.family != socket.AF_INET:
                continue
            if a.address.startswith('127.') or a.address.startswith('169.254.'):
                continue
            try:
                addr_obj = ipaddress.IPv4Address(a.address)
                if addr_obj.is_private:
                    net = ipaddress.IPv4Network(f"{a.address}/{a.netmask}", strict=False)
                    return iface_name, a.address, str(net), "unknown"
            except Exception:
                continue

    return None


# ---------------------------------------------------------------------------
# ARP table reader
# ---------------------------------------------------------------------------

def _read_arp_table(iface_name: str) -> Dict[str, str]:
    """
    Returns {ip: normalized_mac} for dynamic unicast entries on the given interface.
    Reads from OS ARP cache; no packets sent.
    """
    result: Dict[str, str] = {}
    try:
        r = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
    except Exception as e:
        logger.warning(f"arp -a failed: {e}")
        return result

    current_iface_section = False
    for line in r.stdout.splitlines():
        # Windows section header: "Interface: 192.168.31.49 --- 0xd"
        if line.strip().startswith('Interface:'):
            # Check if this section belongs to our interface by IP
            current_iface_section = iface_name.lower() in line.lower() or True
            # We'll filter by IP later if needed
            continue
        if 'dynamic' not in line.lower():
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        ip_str = parts[0]
        mac_raw = parts[1]

        # Exclude multicast/broadcast IPs
        try:
            ip_obj = ipaddress.IPv4Address(ip_str)
            if ip_obj.is_multicast or ip_obj == ipaddress.IPv4Address('255.255.255.255'):
                continue
        except Exception:
            continue

        mac = _normalize_mac(mac_raw)
        if mac:
            result[ip_str] = mac

    return result


# ---------------------------------------------------------------------------
# ICMP ping sweep (stimulates ARP cache population)
# ---------------------------------------------------------------------------

def _ping_host(ip: str, timeout_ms: int) -> bool:
    """Send a single ICMP echo to ip. Returns True if reachable."""
    try:
        if os.name == 'nt':
            r = subprocess.run(
                ['ping', '-n', '1', '-w', str(timeout_ms), ip],
                capture_output=True, text=True, timeout=timeout_ms / 1000 + 2
            )
            return 'TTL=' in r.stdout or 'bytes=' in r.stdout
        else:
            r = subprocess.run(
                ['ping', '-c', '1', '-W', '1', ip],
                capture_output=True, text=True, timeout=timeout_ms / 1000 + 2
            )
            return r.returncode == 0
    except Exception:
        return False


def _icmp_sweep(
    subnet: ipaddress.IPv4Network,
    local_ip: str,
    stop_event: threading.Event,
    timeout_ms: int,
    max_workers: int,
) -> List[str]:
    """
    Ping all hosts in subnet concurrently.
    Returns list of IP strings that responded.
    """
    hosts = list(subnet.hosts())
    # Exclude our own IP from the sweep
    hosts = [h for h in hosts if str(h) != local_ip]

    reachable: List[str] = []

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for h in hosts:
                if stop_event.is_set():
                    break
                try:
                    futures[pool.submit(_ping_host, str(h), timeout_ms)] = str(h)
                except RuntimeError:
                    # Interpreter shutting down or pool closed
                    break
            for future in as_completed(futures):
                if stop_event.is_set():
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                ip = futures[future]
                try:
                    if future.result():
                        reachable.append(ip)
                except Exception:
                    pass
    except (RuntimeError, ValueError) as ex:
        logger.debug(f"ICMP sweep halted during shutdown: {ex}")

    return reachable



# ---------------------------------------------------------------------------
# Hostname resolution
# ---------------------------------------------------------------------------

def _resolve_hostname(ip: str) -> Optional[str]:
    """Best-effort reverse DNS. Returns None if unresolvable."""
    try:
        name = socket.gethostbyaddr(ip)[0]
        # Reject names that are just the IP itself
        if name == ip:
            return None
        return name
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main collector class
# ---------------------------------------------------------------------------

class DeviceDiscoveryCollector:
    """
    Background device discovery worker.
    Runs exactly one scan thread at a time.
    On each cycle:
      1. Read OS ARP table.
      2. ICMP sweep to stimulate ARP cache.
      3. Re-read ARP table.
      4. Resolve hostnames.
      5. Call the registered on_scan_complete callback with results.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_scan_complete: Optional[Callable[[ScanResult], None]] = None

        self._status = "IDLE"          # IDLE / SCANNING / ERROR / UNAVAILABLE
        self._last_scan_result: Optional[ScanResult] = None
        self._scan_in_progress = False

    def register_callback(self, cb: Callable[[ScanResult], None]) -> None:
        self._on_scan_complete = cb

    # --- Public state accessors ---

    @property
    def status(self) -> str:
        return self._status

    @property
    def last_scan_result(self) -> Optional[ScanResult]:
        return self._last_scan_result

    @property
    def scan_in_progress(self) -> bool:
        return self._scan_in_progress

    # --- Lifecycle ---

    def start(self) -> None:
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker_loop, daemon=True, name="DeviceDiscovery"
            )
            self._thread.start()
        logger.info(
            f"DeviceDiscoveryCollector started "
            f"(interval={settings.DEVICE_DISCOVERY_INTERVAL_SECONDS}s)"
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        with self._lock:
            self._is_running = False
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        logger.info("DeviceDiscoveryCollector stopped.")

    def trigger_scan(self) -> bool:
        """
        Trigger an immediate scan (for manual /api/devices/scan).
        Returns True if a scan was started, False if one is already running.
        """
        if self._scan_in_progress:
            return False
        t = threading.Thread(target=self._run_scan, daemon=True, name="DeviceDiscoveryScan")
        t.start()
        return True

    # --- Worker ---

    def _worker_loop(self) -> None:
        """Runs scans at DEVICE_DISCOVERY_INTERVAL_SECONDS intervals."""
        # Small initial delay so startup telemetry worker gets priority
        self._stop_event.wait(timeout=5.0)
        while not self._stop_event.is_set():
            self._run_scan()
            self._stop_event.wait(timeout=float(settings.DEVICE_DISCOVERY_INTERVAL_SECONDS))

    def _run_scan(self) -> None:
        """Execute one complete discovery cycle."""
        with self._lock:
            if self._scan_in_progress:
                return
            self._scan_in_progress = True

        self._status = "SCANNING"
        start = time.time()
        result = ScanResult()

        try:
            iface_info = _select_lan_interface()
            if not iface_info:
                result.error = "No active LAN interface detected."
                result.limitation = "No suitable network interface found. Check your network connection."
                self._status = "UNAVAILABLE"
                self._last_scan_result = result
                logger.warning("DeviceDiscovery: No LAN interface found.")
                return

            iface_name, local_ip, subnet_cidr, gateway_ip = iface_info
            result.interface = iface_name
            result.subnet = subnet_cidr
            result.method = "arp_table+icmp_sweep"

            net = ipaddress.IPv4Network(subnet_cidr, strict=False)
            host_count = net.num_addresses - 2

            if host_count > settings.DEVICE_MAX_AUTO_SCAN_HOSTS:
                result.limitation = (
                    f"Subnet {subnet_cidr} has {host_count} hosts "
                    f"(limit {settings.DEVICE_MAX_AUTO_SCAN_HOSTS}). "
                    f"Set DEVICE_MAX_AUTO_SCAN_HOSTS env var to override."
                )
                result.method = "arp_table_only"
                result.error = None
                logger.warning(f"DeviceDiscovery: {result.limitation}")
                # Fall through to ARP-table-only mode

            # Step 1: initial ARP read
            arp1 = _read_arp_table(iface_name)
            logger.debug(f"DeviceDiscovery: ARP pass 1: {len(arp1)} entries")

            # Step 2: ICMP sweep (only if subnet is within bounds)
            if host_count <= settings.DEVICE_MAX_AUTO_SCAN_HOSTS:
                logger.debug(f"DeviceDiscovery: ICMP sweep {subnet_cidr} ({host_count} hosts)")
                _icmp_sweep(
                    net, local_ip, self._stop_event,
                    settings.DEVICE_PING_SWEEP_TIMEOUT_MS,
                    settings.DEVICE_PING_SWEEP_WORKERS
                )
                # Step 3: re-read ARP table after sweep
                arp2 = _read_arp_table(iface_name)
                # Merge: arp1 + arp2 (ARP gives richer MAC info)
                merged_arp = {**arp1, **arp2}
            else:
                merged_arp = arp1

            logger.debug(f"DeviceDiscovery: merged ARP: {len(merged_arp)} entries")

            # Step 4: build device list
            devices: List[DiscoveredDevice] = []
            for ip, mac in merged_arp.items():
                if self._stop_event.is_set():
                    break
                hostname = _resolve_hostname(ip)
                devices.append(DiscoveredDevice(
                    ip=ip, mac=mac, hostname=hostname, interface=iface_name
                ))

            result.devices = devices
            result.duration_seconds = round(time.time() - start, 2)
            self._last_scan_result = result
            self._status = "IDLE"

            logger.info(
                f"DeviceDiscovery: scan complete in {result.duration_seconds}s — "
                f"{len(devices)} device(s) on {subnet_cidr} via {iface_name}"
            )

            # Notify service layer
            if self._on_scan_complete:
                try:
                    self._on_scan_complete(result)
                except Exception as e:
                    logger.error(f"DeviceDiscovery: callback error: {e}", exc_info=True)

        except Exception as e:
            result.error = str(e)
            result.duration_seconds = round(time.time() - start, 2)
            self._status = "ERROR"
            self._last_scan_result = result
            logger.error(f"DeviceDiscovery: scan error: {e}", exc_info=True)

        finally:
            with self._lock:
                self._scan_in_progress = False


# Global singleton
device_discovery = DeviceDiscoveryCollector()
