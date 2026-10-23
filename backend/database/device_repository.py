# -*- coding: utf-8 -*-
"""Device Repository — SQLite persistence for discovered LAN devices (Phase 9).

Identity strategy:
  - When MAC is available: find existing device by MAC, update IP if changed.
  - When MAC is unavailable: find by (interface, IP) as a fallback.
    This is documented as unstable for DHCP environments but is the best
    we can do without a layer-2 address.

Devices are never deleted. Offline devices are retained with status=OFFLINE.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from backend.database.models import DeviceModel
import logging

logger = logging.getLogger("netwatch.db.device_repo")


class DeviceRepository:

    # ------------------------------------------------------------------ #
    # Read                                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_all(
        db: Session,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> List[DeviceModel]:
        q = db.query(DeviceModel)
        if status:
            q = q.filter(DeviceModel.status == status.upper())
        if search:
            term = f"%{search.lower()}%"
            q = q.filter(or_(
                DeviceModel.ip_address.ilike(term),
                DeviceModel.mac_address.ilike(term),
                DeviceModel.hostname.ilike(term),
            ))
        return q.order_by(DeviceModel.last_seen.desc()).limit(min(limit, 1000)).all()

    @staticmethod
    def get_total(db: Session) -> int:
        return db.query(func.count(DeviceModel.id)).scalar() or 0

    @staticmethod
    def get_by_id(db: Session, device_id: int) -> Optional[DeviceModel]:
        return db.query(DeviceModel).filter(DeviceModel.id == device_id).first()

    @staticmethod
    def get_by_mac(db: Session, mac: str) -> Optional[DeviceModel]:
        return db.query(DeviceModel).filter(DeviceModel.mac_address == mac).first()

    @staticmethod
    def get_by_ip_iface(db: Session, ip: str, iface: str) -> Optional[DeviceModel]:
        return db.query(DeviceModel).filter(
            DeviceModel.ip_address == ip,
            DeviceModel.interface_name == iface
        ).first()

    @staticmethod
    def count_online(db: Session) -> int:
        return db.query(func.count(DeviceModel.id)).filter(
            DeviceModel.status == "ONLINE"
        ).scalar() or 0

    # ------------------------------------------------------------------ #
    # Write                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def upsert_device(
        db: Session,
        *,
        mac: Optional[str],
        ip: str,
        hostname: Optional[str],
        interface_name: str,
        now_ts: float,
        now_iso: str,
    ) -> DeviceModel:
        """Insert or update a device record.

        Lookup order:
          1. MAC address (most stable identity)
          2. IP + interface (fallback when MAC is unavailable)

        Returns the persisted DeviceModel.
        """
        existing: Optional[DeviceModel] = None

        if mac:
            existing = DeviceRepository.get_by_mac(db, mac)
            if existing is None:
                # MAC unknown to us but IP may already exist without MAC — unify if found
                by_ip = DeviceRepository.get_by_ip_iface(db, ip, interface_name)
                if by_ip and by_ip.mac_address is None:
                    # Assign MAC to the IP-only record
                    existing = by_ip
        else:
            existing = DeviceRepository.get_by_ip_iface(db, ip, interface_name)

        if existing:
            # Update mutable fields
            if mac and existing.mac_address is None:
                existing.mac_address = mac
            if existing.ip_address != ip:
                logger.info(f"Device {mac or ip}: IP changed {existing.ip_address} -> {ip}")
                existing.ip_address = ip
            if hostname and existing.hostname != hostname:
                existing.hostname = hostname
            existing.last_seen = now_ts
            existing.last_seen_utc = now_iso
            existing.status = "ONLINE"
            existing.missed_scan_count = 0
            db.commit()
            return existing

        # New device
        device = DeviceModel(
            mac_address=mac,
            ip_address=ip,
            hostname=hostname,
            interface_name=interface_name,
            first_seen=now_ts,
            first_seen_utc=now_iso,
            last_seen=now_ts,
            last_seen_utc=now_iso,
            status="ONLINE",
            missed_scan_count=0,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        logger.info(f"New device discovered: mac={mac} ip={ip} iface={interface_name}")
        return device

    @staticmethod
    def mark_missed(db: Session, device: DeviceModel, offline_threshold: int) -> None:
        """Increment missed scan count; mark OFFLINE once threshold is crossed."""
        device.missed_scan_count += 1
        if device.missed_scan_count >= offline_threshold:
            device.status = "OFFLINE"
        db.commit()

    @staticmethod
    def get_online_devices(db: Session) -> List[DeviceModel]:
        return db.query(DeviceModel).filter(
            DeviceModel.status.in_(["ONLINE", "UNKNOWN"])
        ).all()


device_repo = DeviceRepository()
