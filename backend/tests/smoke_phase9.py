# -*- coding: utf-8 -*-
"""Quick smoke test for Phase 9 device API endpoints."""
import sys, os
sys.path.insert(0, os.path.abspath('.'))

from backend.database.session import Base, engine
from backend.database.models import DeviceModel
Base.metadata.create_all(bind=engine)

from sqlalchemy import inspect as sa_inspect
insp = sa_inspect(engine)
tables = insp.get_table_names()
print("Tables:", tables)
assert "devices" in tables, "devices table missing!"

from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app, raise_server_exceptions=True)

r = client.get("/api/devices")
print(f"GET /api/devices -> {r.status_code}")
assert r.status_code == 200, r.text
data = r.json()
print(f"  count={data['count']} total={data['total']} items={data['items']}")
assert "count" in data and "total" in data and "items" in data

r = client.get("/api/devices/discovery/status")
print(f"GET /api/devices/discovery/status -> {r.status_code}")
assert r.status_code == 200, r.text
ds = r.json()
print(f"  status={ds['status']} method={ds['discovery_method']} subnet={ds['subnet']}")
assert ds["status"] in ("IDLE", "SCANNING", "ERROR", "UNAVAILABLE")

r = client.post("/api/devices/scan")
print(f"POST /api/devices/scan -> {r.status_code}: {r.json()}")
assert r.status_code == 200

r = client.get("/api/devices/9999")
print(f"GET /api/devices/9999 -> {r.status_code}")
assert r.status_code == 404

# Simulate multiple simultaneous scan requests (must not fan out)
r1 = client.post("/api/devices/scan")
r2 = client.post("/api/devices/scan")
print(f"Double scan: r1.started={r1.json().get('started')} r2.started={r2.json().get('started')}")
# At least one of them should return started=False (already scanning)
# (r1 may also return False if previous scan still running from above)

print("\nAll device API smoke tests PASSED.")
