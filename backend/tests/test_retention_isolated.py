import sys
sys.path.insert(0, r'c:\Users\navan\OneDrive\Desktop\NetWatch AI')

import unittest
import os
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.session import Base
from backend.database.models import (
    SystemMetricModel,
    NetworkMetricModel,
    InterfaceMetricModel,
    LatencyMetricModel,
    ProtocolMetricModel,
    AlertModel,
    DeviceModel,
)
from backend.core.config import settings

class TestRetentionIsolated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_file = "test_retention_temp.db"
        if os.path.exists(cls.test_db_file):
            os.remove(cls.test_db_file)
        cls.engine = create_engine(f"sqlite:///{cls.test_db_file}", echo=False)
        Base.metadata.create_all(bind=cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        if os.path.exists(cls.test_db_file):
            os.remove(cls.test_db_file)

    def test_isolated_retention_pruning(self):
        db = self.Session()
        now = time.time()
        # Expired: 10 days ago (retention is 7 days)
        expired_ts = now - (10 * 86400)
        # Recent: 2 days ago
        recent_ts = now - (2 * 86400)

        # 1. Insert expired and recent records across all tables
        # System
        db.add(SystemMetricModel(sample_id="sys-old", timestamp=expired_ts, timestamp_utc="old"))
        db.add(SystemMetricModel(sample_id="sys-new", timestamp=recent_ts, timestamp_utc="new"))
        # Network
        db.add(NetworkMetricModel(sample_id="net-old", timestamp=expired_ts, timestamp_utc="old", bytes_recv=0, bytes_sent=0, packets_recv=0, packets_sent=0))
        db.add(NetworkMetricModel(sample_id="net-new", timestamp=recent_ts, timestamp_utc="new", bytes_recv=0, bytes_sent=0, packets_recv=0, packets_sent=0))
        # Interface
        db.add(InterfaceMetricModel(sample_id="if-old", timestamp=expired_ts, timestamp_utc="old", interface_name="eth0", bytes_recv=0, bytes_sent=0, packets_recv=0, packets_sent=0))
        db.add(InterfaceMetricModel(sample_id="if-new", timestamp=recent_ts, timestamp_utc="new", interface_name="eth0", bytes_recv=0, bytes_sent=0, packets_recv=0, packets_sent=0))
        # Latency
        db.add(LatencyMetricModel(probe_id="lat-old", timestamp=expired_ts, timestamp_utc="old", target="1.1.1.1"))
        db.add(LatencyMetricModel(probe_id="lat-new", timestamp=recent_ts, timestamp_utc="new", target="1.1.1.1"))
        # Protocol
        db.add(ProtocolMetricModel(window_id="proto-old", timestamp=expired_ts, timestamp_utc="old"))
        db.add(ProtocolMetricModel(window_id="proto-new", timestamp=recent_ts, timestamp_utc="new"))
        # Lifecycle items (Alerts & Devices)
        db.add(AlertModel(alert_id="alt-old", type="CPU", severity="WARNING", status="OPEN", source="host", message="old alert", metric_name="cpu", opened_at=expired_ts, opened_at_utc="old", last_seen_at=expired_ts, last_seen_at_utc="old"))
        db.add(DeviceModel(mac_address="aa:bb:cc:dd:ee:01", ip_address="192.168.1.10", interface_name="Wi-Fi", first_seen=expired_ts, first_seen_utc="old", last_seen=expired_ts, last_seen_utc="old"))
        db.commit()

        # Verify initial counts
        self.assertEqual(db.query(SystemMetricModel).count(), 2)
        self.assertEqual(db.query(NetworkMetricModel).count(), 2)
        self.assertEqual(db.query(InterfaceMetricModel).count(), 2)
        self.assertEqual(db.query(LatencyMetricModel).count(), 2)
        self.assertEqual(db.query(ProtocolMetricModel).count(), 2)
        self.assertEqual(db.query(AlertModel).count(), 1)
        self.assertEqual(db.query(DeviceModel).count(), 1)

        # 2. Run retention purge function
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=settings.TELEMETRY_RETENTION_DAYS)).timestamp()
        db.query(SystemMetricModel).filter(SystemMetricModel.timestamp < cutoff_ts).delete()
        db.query(NetworkMetricModel).filter(NetworkMetricModel.timestamp < cutoff_ts).delete()
        db.query(InterfaceMetricModel).filter(InterfaceMetricModel.timestamp < cutoff_ts).delete()
        db.query(LatencyMetricModel).filter(LatencyMetricModel.timestamp < cutoff_ts).delete()
        db.query(ProtocolMetricModel).filter(ProtocolMetricModel.timestamp < cutoff_ts).delete()
        db.commit()

        # 3. Verify expired removed, recent preserved, lifecycle items untouched
        self.assertEqual(db.query(SystemMetricModel).count(), 1)
        self.assertEqual(db.query(SystemMetricModel).first().sample_id, "sys-new")
        self.assertEqual(db.query(NetworkMetricModel).count(), 1)
        self.assertEqual(db.query(NetworkMetricModel).first().sample_id, "net-new")
        self.assertEqual(db.query(InterfaceMetricModel).count(), 1)
        self.assertEqual(db.query(InterfaceMetricModel).first().sample_id, "if-new")
        self.assertEqual(db.query(LatencyMetricModel).count(), 1)
        self.assertEqual(db.query(LatencyMetricModel).first().probe_id, "lat-new")
        self.assertEqual(db.query(ProtocolMetricModel).count(), 1)
        self.assertEqual(db.query(ProtocolMetricModel).first().window_id, "proto-new")

        # Crucial: Alerts and devices were NOT pruned
        self.assertEqual(db.query(AlertModel).count(), 1)
        self.assertEqual(db.query(DeviceModel).count(), 1)

        # 4. Repeat cleanup (idempotency / safety test)
        db.query(SystemMetricModel).filter(SystemMetricModel.timestamp < cutoff_ts).delete()
        db.query(NetworkMetricModel).filter(NetworkMetricModel.timestamp < cutoff_ts).delete()
        db.query(InterfaceMetricModel).filter(InterfaceMetricModel.timestamp < cutoff_ts).delete()
        db.query(LatencyMetricModel).filter(LatencyMetricModel.timestamp < cutoff_ts).delete()
        db.query(ProtocolMetricModel).filter(ProtocolMetricModel.timestamp < cutoff_ts).delete()
        db.commit()

        self.assertEqual(db.query(SystemMetricModel).count(), 1)
        self.assertEqual(db.query(NetworkMetricModel).count(), 1)
        self.assertEqual(db.query(InterfaceMetricModel).count(), 1)
        self.assertEqual(db.query(LatencyMetricModel).count(), 1)
        self.assertEqual(db.query(ProtocolMetricModel).count(), 1)
        db.close()

if __name__ == '__main__':
    unittest.main()
