import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=True)

r = client.get("/api/alerts/summary")
assert r.status_code == 200
s = r.json()
print("GET /api/alerts/summary:", r.status_code)
print("  total_active=%d open=%d critical=%d" % (s["total_active"], s["open_count"], s["critical_count"]))

r2 = client.get("/api/alerts?limit=5")
assert r2.status_code == 200
d = r2.json()
print("GET /api/alerts:", r2.status_code, "returned=%d" % d["count"])

r4 = client.get("/api/health-score")
assert r4.status_code == 200
hs = r4.json()
print("GET /api/health-score:", r4.status_code)
print("  score=%d status=%s deductions=%d" % (hs["score"], hs["status"], len(hs["deductions"])))
for dd in hs["deductions"]:
    print("    [%s] -%d pts: %s" % (dd["category"], dd["points"], dd["reason"]))

assert 0 <= hs["score"] <= 100, "Score out of range!"
assert hs["status"] in ("HEALTHY", "DEGRADED", "POOR", "CRITICAL"), "Unknown status"
print("\nAll Phase 8 API endpoints: PASSED")
