"""
Phase 13.1 Security Hardening Tests:
1. CORS:
   - Allowed origins receive Access-Control-Allow-Origin matching the origin
   - Disallowed origins do not receive allow-origin
   - Preflight OPTIONS returns expected methods & headers
   - Credentialed CORS is preserved with specific origins (no wildcard)
2. Operator Authorization:
   - Valid key -> 200 OK
   - Missing key when key is configured -> 401 Unauthorized
   - Invalid key -> 401 Unauthorized
   - Production mode with no key -> 403 Forbidden
   - Development mode with no key -> Permitted (local dev convenience)
   - Read-only endpoints (/api/system/current, /api/devices, etc.) remain open
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings

client = TestClient(app)


# ─── 1. CORS Tests ────────────────────────────────────────────────────────────

def test_cors_allowed_origin():
    """Verify configured origin receives correct CORS headers and credentials flag."""
    origin = "http://localhost:5173"
    res = client.get("/api/health", headers={"Origin": origin})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin
    assert res.headers.get("access-control-allow-credentials") == "true"


def test_cors_disallowed_origin():
    """Verify unauthorized origin does NOT receive an allow-origin header authorizing it."""
    origin = "http://evil-attacker.com"
    res = client.get("/api/health", headers={"Origin": origin})
    assert res.status_code == 200
    # Must NOT authorize the evil origin
    assert res.headers.get("access-control-allow-origin") != origin
    assert res.headers.get("access-control-allow-origin") != "*"


def test_cors_preflight_options():
    """Verify preflight OPTIONS request returns required methods and headers."""
    origin = "http://localhost:5173"
    res = client.options(
        "/api/devices/scan",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-NetWatch-Key,Content-Type",
        }
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin
    allow_methods = res.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods
    allow_headers = res.headers.get("access-control-allow-headers", "")
    assert "x-netwatch-key" in allow_headers.lower()


def test_cors_config_parsing_missing_and_malformed():
    """Verify Settings parses clean comma-separated origins and defaults safely when empty."""
    from backend.core.config import Settings
    import os

    # Default when env unset
    s_default = Settings()
    assert "http://localhost:5173" in s_default.CORS_ORIGINS
    assert "*" not in s_default.CORS_ORIGINS

    # Custom valid origins
    os.environ["CORS_ORIGINS"] = "https://dashboard.local, https://monitor.company.internal"
    try:
        s_custom = Settings()
        assert s_custom.CORS_ORIGINS == ["https://dashboard.local", "https://monitor.company.internal"]
    finally:
        os.environ.pop("CORS_ORIGINS", None)

    # Malformed/whitespace-heavy input
    os.environ["CORS_ORIGINS"] = "  https://site1.com , ,  https://site2.com  "
    try:
        s_malformed = Settings()
        assert s_malformed.CORS_ORIGINS == ["https://site1.com", "https://site2.com"]
    finally:
        os.environ.pop("CORS_ORIGINS", None)


# ─── 2. Operator Authorization Tests ──────────────────────────────────────────

def test_operator_auth_configured_valid_key(monkeypatch):
    """When API_KEY is configured, valid X-NetWatch-Key succeeds."""
    monkeypatch.setattr(settings, "API_KEY", "secret-test-key-123")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Devices scan
    res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "secret-test-key-123"})
    assert res.status_code == 200
    assert "started" in res.json()


def test_operator_auth_configured_missing_key(monkeypatch):
    """When API_KEY is configured, missing header returns 401 Unauthorized."""
    monkeypatch.setattr(settings, "API_KEY", "secret-test-key-123")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    res = client.post("/api/devices/scan")
    assert res.status_code == 401
    assert "missing" in res.json()["detail"].lower()


def test_operator_auth_configured_invalid_key(monkeypatch):
    """When API_KEY is configured, wrong header returns 401 Unauthorized."""
    monkeypatch.setattr(settings, "API_KEY", "secret-test-key-123")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "wrong-key"})
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_operator_auth_production_fail_closed(monkeypatch):
    """In production mode with unset API_KEY, mutating endpoints are denied with 403."""
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    res = client.post("/api/devices/scan")
    assert res.status_code == 403
    assert "disabled" in res.json()["detail"].lower()


def test_readonly_endpoints_remain_unauthenticated():
    """Verify read-only endpoints (telemetry, devices, alerts) are never blocked."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/system/current").status_code == 200
    assert client.get("/api/devices").status_code == 200
    assert client.get("/api/alerts").status_code == 200
    assert client.get("/api/analytics/coverage").status_code == 200


def test_operator_auth_acknowledge_endpoint(monkeypatch):
    """Verify POST /api/alerts/{id}/acknowledge enforces operator auth when configured."""
    monkeypatch.setattr(settings, "API_KEY", "operator-alert-key")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Missing auth
    res_missing = client.post("/api/alerts/1/acknowledge")
    assert res_missing.status_code == 401

    # Invalid auth
    res_invalid = client.post("/api/alerts/1/acknowledge", headers={"X-NetWatch-Key": "bad-key"})
    assert res_invalid.status_code == 401

    # In production without key -> 403
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    res_prod = client.post("/api/alerts/1/acknowledge")
    assert res_prod.status_code == 403


def test_unauthorized_request_cannot_trigger_cooldown(monkeypatch):
    """Verify unauthorized calls are rejected with 401 before cooldown is evaluated or consumed."""
    import backend.api.devices as devices_module
    devices_module._last_manual_scan_ts = 0.0

    monkeypatch.setattr(settings, "API_KEY", "cooldown-auth-key")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    # Unauthenticated request returns 401, not 429
    res_unauth = client.post("/api/devices/scan")
    assert res_unauth.status_code == 401

    # Timestamp must not have been set/touched
    assert devices_module._last_manual_scan_ts == 0.0

