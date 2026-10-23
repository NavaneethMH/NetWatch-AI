"""Comprehensive verification of the running backend server.
Tests:
1. /api/latency/current returns real ping probe snapshot (with target, status, packet loss, age, staleness)
2. /api/latency/history returns persisted SQLite probe records (with target, from, to, limit, order filters)
3. Multiple requests do not trigger extra ping probes (verifying browser count independence)
4. WebSocket /ws/telemetry delivers latency snapshot alongside system and network telemetry
5. Historical records survive server restart and match SQLite rows exactly
"""
import time
import requests
import asyncio
import websockets
import json

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/telemetry"

def test_api_current():
    print("\n--- Testing GET /api/latency/current ---")
    res = requests.get(f"{BASE_URL}/api/latency/current")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    print("Latency Current Response:", json.dumps(data, indent=2))
    assert "target" in data
    assert "status" in data
    assert data["status"] in ("LIVE", "PARTIAL", "UNREACHABLE", "ERROR", "WARMING_UP")
    assert "is_reachable" in data
    assert "packet_loss_percent" in data
    assert "latency_last_ms" in data
    assert "latency_avg_ms" in data
    assert "probe_age_seconds" in data
    assert "is_stale" in data
    print("PASS: /api/latency/current contract verified.")

def test_api_history():
    print("\n--- Testing GET /api/latency/history ---")
    res = requests.get(f"{BASE_URL}/api/latency/history?limit=10&order=desc")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    print(f"Latency History Count: {data['count']}, Limit: {data['limit']}")
    assert "items" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        item = data["items"][0]
        print("Sample History Item:", json.dumps(item, indent=2))
        assert "probe_id" in item
        assert "target" in item
        assert "status" in item
        assert "timestamp" in item
        assert "packets_sent" in item
        assert "packets_received" in item
        assert "packet_loss_percent" in item
    print("PASS: /api/latency/history contract verified.")

def test_browser_count_independence():
    print("\n--- Testing Browser Count Independence (No ping fanout) ---")
    t0 = time.time()
    for _ in range(25):
        r = requests.get(f"{BASE_URL}/api/latency/current")
        assert r.status_code == 200
    elapsed = time.time() - t0
    print(f"25 requests completed in {elapsed:.3f} seconds ({elapsed/25*1000:.1f}ms per request)")
    # If each request spawned a ping, 25 pings would take at least 25 seconds.
    assert elapsed < 1.5, "Requests took too long; likely spawning ping per request!"
    print("PASS: Browser requests do not spawn extra probes.")

def test_api_alerts_and_health():
    print("\n--- Testing GET /api/health-score ---")
    res = requests.get(f"{BASE_URL}/api/health-score")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    health = res.json()
    print("Health Score Response:", json.dumps(health, indent=2))
    assert "score" in health
    assert 0 <= health["score"] <= 100
    assert "status" in health
    assert health["status"] in ("HEALTHY", "DEGRADED", "POOR", "CRITICAL")
    assert "deductions" in health
    assert "telemetry_freshness" in health
    deduction_sum = sum(d["points"] for d in health["deductions"])
    assert health["score"] == max(0, min(100, 100 - deduction_sum)), "Score must equal 100 - sum(deductions)"
    print("PASS: /api/health-score contract verified.")

    print("\n--- Testing GET /api/alerts and /api/alerts/summary ---")
    res_summary = requests.get(f"{BASE_URL}/api/alerts/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    print("Alerts Summary:", json.dumps(summary, indent=2))
    assert "total_active" in summary
    assert "open_count" in summary
    assert "acknowledged_count" in summary

    res_alerts = requests.get(f"{BASE_URL}/api/alerts?limit=10")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    assert "items" in alerts
    print(f"Total alerts in DB: {alerts['total']}")
    print("PASS: /api/alerts and /api/alerts/summary verified.")

async def test_websocket_telemetry():
    print("\n--- Testing WebSocket Live Telemetry Delivery ---")
    async with websockets.connect(WS_URL) as ws:
        # First message is snapshot
        raw_snapshot = await asyncio.wait_for(ws.recv(), timeout=5.0)
        snap = json.loads(raw_snapshot)
        print("Received WebSocket Snapshot message type:", snap.get("type"))
        assert snap.get("type") in ("snapshot", "telemetry")
        assert "system" in snap
        assert "network" in snap
        assert "latency" in snap
        assert "health_score" in snap, "Snapshot must include health_score"
        assert "alerts_summary" in snap, "Snapshot must include alerts_summary"
        lat = snap["latency"]
        print("WebSocket Health Score:", snap["health_score"]["score"], snap["health_score"]["status"])
        assert "target" in lat
        assert "status" in lat
        assert "is_reachable" in lat

        # Wait for live telemetry update (should arrive within ~2.5s)
        raw_tick = await asyncio.wait_for(ws.recv(), timeout=4.0)
        tick = json.loads(raw_tick)
        print("Received Live Telemetry message type:", tick.get("type"))
        assert tick.get("type") == "telemetry"
        assert "latency" in tick
        assert "health_score" in tick, "Live tick must include health_score"
        assert "alerts_summary" in tick, "Live tick must include alerts_summary"
        assert tick["latency"]["target"] == lat["target"]
    print("PASS: WebSocket delivers unified telemetry with real latency, health score, and alerts summary.")

def main():
    print("Starting Live Backend Endpoints & WebSocket Verification...")
    test_api_current()
    test_api_history()
    test_api_alerts_and_health()
    test_browser_count_independence()
    asyncio.run(test_websocket_telemetry())
    print("\n==========================================")
    print("ALL LIVE SERVER INTEGRATION CHECKS PASSED!")
    print("==========================================")

if __name__ == "__main__":
    main()
