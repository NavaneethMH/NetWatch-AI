# -*- coding: utf-8 -*-
"""Device Service — bridges discovery collector and database (Phase 9).

Responsibilities:
  - Receives ScanResult callbacks from DeviceDiscoveryCollector.
  - Upserts discovered devices via DeviceRepository (MAC-first identity).
  - Marks previously-online devices as missed/offline when absent.
  - Provides read methods for the API layer.
  - Never fabricates devices or modifies the telemetry worker cadence.
"""
from __future__ import annotations

import time
import logging
from datetime import datetime, timezone
from typing import List, Optional

from backend.collectors.device_discovery import (
    DeviceDiscoveryCollector,
    ScanResult,
    device_discovery,
)
from backend.database.device_repository import device_repo
from backend.database.models import DeviceModel
from backend.database.session import SessionLocal
from backend.schemas.device import (
    DeviceItem,
    DeviceListResponse,
    DiscoveryStatus,
    DeviceSummary,
)
from backend.core.config import settings

logger = logging.getLogger("netwatch.services.device")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DeviceService:

    def __init__(self, collector: DeviceDiscoveryCollector):
        self._collector = collector
        collector.register_callback(self._on_scan_complete)

    # ------------------------------------------------------------------ #
    # Callback from collector (runs in the discovery thread)               #
    # ------------------------------------------------------------------ #

    def _on_scan_complete(self, result: ScanResult) -> None:
        """Persist scan results to SQLite via repository."""
        db = SessionLocal()
        try:
            now_ts = time.time()
            now_iso = _now_iso()

            # Set of IPs seen this scan (for missed-scan tracking)
            seen_ips = {d.ip for d in result.devices}
            seen_macs = {d.mac for d in result.devices if d.mac}

            # Upsert each discovered device
            for dev in result.devices:
                try:
                    device_repo.upsert_device(
                        db,
                        mac=dev.mac,
                        ip=dev.ip,
                        hostname=dev.hostname,
                        interface_name=dev.interface,
                        now_ts=now_ts,
                        now_iso=now_iso,
                    )
                except Exception as e:
                    logger.error(f"DeviceService: upsert error for {dev.ip}: {e}", exc_info=True)
                    db.rollback()

            # Mark devices that were online but absent this scan
            online_devices = device_repo.get_online_devices(db)
            for existing in online_devices:
                was_seen = (
                    (existing.mac_address and existing.mac_address in seen_macs) or
                    (not existing.mac_address and existing.ip_address in seen_ips)
                )
                if not was_seen:
                    try:
                        device_repo.mark_missed(
                            db, existing,
                            settings.DEVICE_OFFLINE_AFTER_MISSED_SCANS
                        )
                        if existing.missed_scan_count >= settings.DEVICE_OFFLINE_AFTER_MISSED_SCANS:
                            logger.info(
                                f"DeviceService: device mac={existing.mac_address} "
                                f"ip={existing.ip_address} marked OFFLINE after "
                                f"{existing.missed_scan_count} missed scans"
                            )
                    except Exception as e:
                        logger.error(f"DeviceService: mark_missed error: {e}", exc_info=True)
                        db.rollback()

        except Exception as e:
            logger.error(f"DeviceService: scan callback error: {e}", exc_info=True)
        finally:
            db.close()

    # ------------------------------------------------------------------ #
    # API read methods                                                      #
    # ------------------------------------------------------------------ #

    def get_devices(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> DeviceListResponse:
        db = SessionLocal()
        try:
            items = device_repo.get_all(db, status=status, search=search, limit=limit)
            total = device_repo.get_total(db)
            return DeviceListResponse(
                count=len(items),
                total=total,
                items=[DeviceItem.model_validate(d) for d in items],
            )
        finally:
            db.close()

    def get_device_by_id(self, device_id: int) -> Optional[DeviceItem]:
        db = SessionLocal()
        try:
            d = device_repo.get_by_id(db, device_id)
            return DeviceItem.model_validate(d) if d else None
        finally:
            db.close()

    def get_discovery_status(self) -> DiscoveryStatus:
        result = self._collector.last_scan_result
        last_utc = None
        duration = None
        found = None
        iface = None
        subnet = None
        limitation = None
        error = None

        if result:
            last_utc = _now_iso()  # approximate; we don't store scan time separately
            duration = result.duration_seconds
            found = len(result.devices)
            iface = result.interface
            subnet = result.subnet
            limitation = result.limitation
            error = result.error

        return DiscoveryStatus(
            status=self._collector.status,
            discovery_method=result.method if result else "arp_table+icmp_sweep",
            interface=iface,
            subnet=subnet,
            last_scan_utc=last_utc,
            last_scan_duration_seconds=duration,
            devices_found_last_scan=found,
            limitation=limitation,
            error=error,
        )

    def get_device_summary(self) -> DeviceSummary:
        db = SessionLocal()
        try:
            online = device_repo.count_online(db)
            total = device_repo.get_total(db)
        finally:
            db.close()

        result = self._collector.last_scan_result
        last_utc = result.method and _now_iso() if result else None  # type: ignore

        return DeviceSummary(
            online=online,
            known=total,
            discovery_status=self._collector.status,
            last_scan_utc=last_utc,
        )

    def trigger_manual_scan(self) -> bool:
        """Returns True if a new scan was started, False if one is already running."""
        return self._collector.trigger_scan()


# Global singleton — wires collector to service
device_service = DeviceService(device_discovery)
