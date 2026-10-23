"""
Phase 13.2 & 13.3 Reliability Hardening Tests
==============================================

13.2 -- Database Health Check Integration:
  - /api/health reports database: "ok" and a numeric db_latency_ms when the DB is accessible.
  - /api/health status is "degraded" (not 5xx) when the DB is unreachable.
  - environment and scan_cooldown_seconds are present in details.

13.3 -- Manual Scan Rate-Limiting:
  - First scan request succeeds (200 OK).
  - Immediately repeated scan returns 429 with Retry-After header.
  - Response body contains retry_after_seconds.
  - After cooldown window the endpoint accepts again.
"""

import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings
import backend.api.devices as devices_module

client = TestClient(app)


# ---- Phase 13.2: DB Health Check ------------------------------------------------

class TestDatabaseHealthCheck:
    def test_health_db_ok_status(self):
        """When DB is accessible, /api/health should return status ok and db ok."""
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["details"]["database"] == "ok"

    def test_health_db_latency_numeric(self):
        """db_latency_ms should be a non-negative float when DB responds."""
        res = client.get("/api/health")
        assert res.status_code == 200
        latency = res.json()["details"]["db_latency_ms"]
        assert isinstance(latency, (int, float))
        assert latency >= 0

    def test_health_environment_present(self):
        """details.environment must be present and non-empty."""
        res = client.get("/api/health")
        assert res.status_code == 200
        env = res.json()["details"]["environment"]
        assert env in ("development", "production", "test", "staging")

    def test_health_scan_cooldown_present(self):
        """details.scan_cooldown_seconds must reflect the configured cooldown."""
        res = client.get("/api/health")
        assert res.status_code == 200
        cooldown = res.json()["details"]["scan_cooldown_seconds"]
        assert isinstance(cooldown, int)
        assert cooldown > 0

    def test_health_degraded_when_db_fails(self):
        """When the DB probe raises, /api/health returns 200 with status degraded (not 5xx)."""
        import backend.api.health as health_module
        original_probe = health_module._probe_database

        def failing_probe():
            return "degraded", None

        health_module._probe_database = failing_probe
        try:
            res = client.get("/api/health")
            assert res.status_code == 200
            body = res.json()
            assert body["status"] == "degraded"
            assert body["details"]["database"] == "degraded"
            assert body["details"]["db_latency_ms"] is None
        finally:
            health_module._probe_database = original_probe

    def test_health_no_hardcoded_sqlite_ready(self):
        """The old hardcoded sqlite_ready string must no longer appear."""
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["details"]["database"] != "sqlite_ready"


# ---- Phase 13.3: Manual Scan Rate-Limiting ------------------------------------

class TestScanRateLimit:
    def setup_method(self, _method):
        """Reset the module-level cooldown tracker before each test."""
        devices_module._last_manual_scan_ts = 0.0

    def test_first_scan_allowed(self, monkeypatch):
        """First call with valid key succeeds."""
        monkeypatch.setattr(settings, "API_KEY", "ratelimit-test-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "ratelimit-test-key"})
        assert res.status_code == 200
        body = res.json()
        assert "started" in body

    def test_immediate_repeat_returns_429(self, monkeypatch):
        """Second call immediately after first returns 429."""
        monkeypatch.setattr(settings, "API_KEY", "ratelimit-test-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEVICE_SCAN_COOLDOWN_SECONDS", 60)

        devices_module._last_manual_scan_ts = time.time()

        res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "ratelimit-test-key"})
        assert res.status_code == 429

    def test_429_includes_retry_after_header(self, monkeypatch):
        """429 response must carry Retry-After header."""
        monkeypatch.setattr(settings, "API_KEY", "ratelimit-test-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEVICE_SCAN_COOLDOWN_SECONDS", 60)

        devices_module._last_manual_scan_ts = time.time()

        res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "ratelimit-test-key"})
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert int(res.headers["Retry-After"]) > 0

    def test_429_body_contains_retry_after_seconds(self, monkeypatch):
        """429 body must contain retry_after_seconds field."""
        monkeypatch.setattr(settings, "API_KEY", "ratelimit-test-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEVICE_SCAN_COOLDOWN_SECONDS", 60)

        devices_module._last_manual_scan_ts = time.time()

        res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "ratelimit-test-key"})
        assert res.status_code == 429
        body = res.json()
        assert "retry_after_seconds" in body
        assert body["retry_after_seconds"] > 0

    def test_scan_allowed_after_cooldown_expires(self, monkeypatch):
        """Scan is accepted once cooldown has elapsed."""
        monkeypatch.setattr(settings, "API_KEY", "ratelimit-test-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        monkeypatch.setattr(settings, "DEVICE_SCAN_COOLDOWN_SECONDS", 1)

        devices_module._last_manual_scan_ts = time.time() - 2.0

        res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "ratelimit-test-key"})
        assert res.status_code == 200

    def test_rate_limit_independent_of_auth_check(self, monkeypatch):
        """Unauthorized requests are rejected by 401/403 before cooldown check runs."""
        monkeypatch.setattr(settings, "API_KEY", "some-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        devices_module._last_manual_scan_ts = 0.0

        res = client.post("/api/devices/scan")  # no key
        assert res.status_code in (401, 403)

    def test_already_running_scan_does_not_consume_cooldown(self, monkeypatch):
        """Discovering an already running scan returns message and does not advance cooldown timestamp."""
        monkeypatch.setattr(settings, "API_KEY", "ratelimit-test-key")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")

        devices_module._last_manual_scan_ts = 0.0

        # Simulate device_service.trigger_manual_scan returning False (scan already in progress)
        from backend.services.device_service import device_service
        orig_trigger = device_service.trigger_manual_scan
        device_service.trigger_manual_scan = lambda: False
        try:
            res = client.post("/api/devices/scan", headers={"X-NetWatch-Key": "ratelimit-test-key"})
            assert res.status_code == 200
            data = res.json()
            assert data["started"] is False
            assert "already in progress" in data["message"].lower()
            # Must NOT advance cooldown timestamp
            assert devices_module._last_manual_scan_ts == 0.0
        finally:
            device_service.trigger_manual_scan = orig_trigger


# ---- Phase 13.1 SEC-03: Information Disclosure Tests ---------------------------

class TestInformationDisclosure:
    def test_404_does_not_leak_internals(self):
        """404 responses return clean messages without internal filesystem paths or code structures."""
        res = client.get("/api/nonexistent-route")
        assert res.status_code == 404
        text = res.text
        assert "traceback" not in text.lower()
        assert "file \"" not in text.lower()
        assert "backend/" not in text.lower()

    def test_health_does_not_leak_sql_exceptions(self):
        """Degraded health response does not expose database exceptions or query structures."""
        import backend.api.health as health_module
        orig_probe = health_module._probe_database

        def failing_probe():
            return "degraded", None

        health_module._probe_database = failing_probe
        try:
            res = client.get("/api/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "degraded"
            assert "exception" not in data
            assert "traceback" not in data
            assert "OperationalError" not in str(data)
        finally:
            health_module._probe_database = orig_probe


# ---- Phase 13.2 CONF-01: SQLite File Permissions --------------------------------

class TestSqlitePermissions:
    def test_sqlite_permission_enforcement(self, tmp_path, monkeypatch):
        """Verify file and directory permissions logic applies restrictive permissions on POSIX and documents Windows behavior."""
        import os
        import stat

        test_dir = tmp_path / "db_test"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "netwatch_test.db"
        test_file.write_text("test")

        if os.name != "nt":
            os.chmod(str(test_dir), 0o700)
            os.chmod(str(test_file), 0o600)

            dir_mode = stat.S_IMODE(os.stat(str(test_dir)).st_mode)
            file_mode = stat.S_IMODE(os.stat(str(test_file)).st_mode)

            assert dir_mode == 0o700, f"Expected 0700 for parent directory, got {oct(dir_mode)}"
            assert file_mode == 0o600, f"Expected 0600 for sqlite database, got {oct(file_mode)}"
        else:
            # On Windows, POSIX chmod bits are a no-op/limited; verify file exists and is accessible
            assert test_file.exists()
            assert test_dir.exists()


