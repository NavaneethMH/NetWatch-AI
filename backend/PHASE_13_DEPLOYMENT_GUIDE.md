# Phase 13 Deployment Guide

This guide describes configuration, installation, security hardening, reverse proxy setup, service management, and operational procedures for deploying NetWatch AI on a single host.

---

## 1. Architectural Overview & Single-Worker Requirement

NetWatch AI uses an in-process, stateful telemetry engine:
1. **Delta Counters:** Monotonic elapsed-time network traffic counters calculate accurate Mbps throughput.
2. **Autonomous Background Workers:** Internal daemon threads continuously sample host telemetry, execute ICMP ping probes, discover LAN devices via ARP table sweeps, poll active socket states via `psutil`, and aggregate link-layer packet metadata in real time.
3. **Single-Worker Invariant:** NetWatch strictly requires **one single worker process** (`workers=1`). Running multi-worker Uvicorn (`--workers > 1`) is unsupported because:
   - Multiple independent threads interleave database transactions.
   - High-frequency delta counter resets across worker processes produce erratic telemetry readings.
   - Separate memory spaces desynchronize connection mappings and WebSocket broadcast pools.

NetWatch scales horizontally by deploying an independent instance per host, never by spawning multiple workers on the same host. A built-in PID guard (`backend/netwatch.pid`) validates that another competing process is not active and cleans up stale PID files gracefully after abnormal termination.

---

## 2. Configuration & Environment Variables

All settings are configured via environment variables and parsed safely by `backend/core/config.py`.

| Variable | Type | Default | Production Requirement | Description |
|---|---|---|---|---|
| `NETWATCH_ENV` | `string` | `development` | Set to `production` | Environment mode (`development`, `production`, `test`). In production, mutating operations fail closed if `NETWATCH_API_KEY` is not set. |
| `NETWATCH_API_KEY` | `string` | `""` (empty) | **Required in production** | Server operator authorization key. Sent via `X-NetWatch-Key` header for protected endpoints (`POST /api/devices/scan`, `POST /api/alerts/{id}/acknowledge`). Compared using constant-time comparison. |
| `CORS_ORIGINS` | `string` | Local origins (`localhost:5173`, `127.0.0.1:5173`, `localhost:8000`, `127.0.0.1:8000`) | Set to explicit frontend domain(s) | Comma-separated list of approved browser origins. Wildcards (`*`) are prohibited when credentials are enabled. |
| `DEVICE_SCAN_COOLDOWN_SECONDS` | `integer` | `60` | Optional | Cooldown period between manual scans requested via `POST /api/devices/scan`. Excessive calls return HTTP `429 Too Many Requests` with `Retry-After`. |
| `WS_MAX_CLIENTS` | `integer` | `20` | Optional | Maximum concurrent WebSocket connections. Enforced atomically via lock; excess attempts close with code `4003 Policy Violation`. |
| `PING_TARGET` | `string` | `1.1.1.1` | Optional | Default ICMP target for latency and packet loss monitoring. |
| `PING_INTERVAL_SECONDS` | `integer` | `5` | Optional | Probe cadence (seconds) for latency collector. |
| `PING_COUNT` | `integer` | `4` | Optional | ICMP ping count per cycle. |
| `DEVICE_DISCOVERY_INTERVAL_SECONDS` | `integer` | `60` | Optional | Interval between automatic LAN ARP sweeps. |
| `DEVICE_MAX_AUTO_SCAN_HOSTS` | `integer` | `512` | Optional | Maximum subnet size allowed for ICMP sweeps. Larger subnets fall back safely to passive ARP table reading. |
| `DEVICE_PING_SWEEP_TIMEOUT_MS` | `integer` | `500` | Optional | Timeout per ping during LAN sweeps. |
| `DEVICE_PING_SWEEP_WORKERS` | `integer` | `32` | Optional | Worker pool size for concurrent discovery ping sweeps. |
| `CONNECTION_SCAN_INTERVAL_SECONDS` | `float` | `5.0` | Optional | Interval between host connection scans (`psutil`). |
| `SAMPLING_INTERVAL_SECONDS` | `float` | `2.0` | Fixed / Optional | Background tick rate for host and interface metrics persistence. |
| `TELEMETRY_RETENTION_DAYS` | `integer` | `7` | Optional | Rolling retention window for time-series metric tables. |
| `CLEANUP_INTERVAL_SECONDS` | `float` | `3600.0` | Optional | Retention pruning cycle frequency (1 hour). |

---

## 3. Security Hardening

### 3.1 Operator Authorization (SEC-02)
- **Protected Endpoints:**
  - `POST /api/devices/scan`
  - `POST /api/alerts/{id}/acknowledge`
- **Fail-Closed Policy:** In production (`NETWATCH_ENV=production`), if `NETWATCH_API_KEY` is empty, requests return HTTP `403 Forbidden` (`Operator actions are disabled: server authorization key is not configured`).
- **Development Convenience:** If `NETWATCH_API_KEY` is left empty in `development` mode, mutations are permitted locally with an audit log message. Once `NETWATCH_API_KEY` is configured in any mode, strict `X-NetWatch-Key` header authentication is enforced.
- **Constant-Time Comparison:** Key matching uses `hmac.compare_digest` to prevent timing attacks.
- **Zero Frontend Secrets:** No operator key is placed in frontend bundle files, `.env` files exposed to Vite, or compiled JavaScript assets. Operators enter their key in the UI session or supply it via browser session storage at runtime.

### 3.2 CORS Hardening (SEC-01)
- Wildcard origins (`*`) are disallowed when `allow_credentials=True`.
- The origin list is parsed into discrete, validated strings.
- Only required HTTP methods (`GET`, `POST`, `OPTIONS`) and headers (`Content-Type`, `Accept`, `Authorization`, `X-NetWatch-Key`) are accepted.

### 3.3 Information Disclosure Prevention (SEC-03)
- Health probe failures return a clean `{"status": "degraded", "database": "degraded"}` payload without raw exception types or tracebacks.
- Database connection strings, SQL queries, and file paths are never exposed in client HTTP responses.

### 3.4 Concurrency-Safe WebSocket Bounding (REL-02)
- WebSocket connections are admitted under an atomic asynchronous lock.
- If current connections reach `WS_MAX_CLIENTS` (default 20), incoming handshakes are rejected with code `4003` (`Maximum connections exceeded`).
- All active client sends enforce a strict 1.5-second timeout, ensuring stalled clients are evicted without blocking broadcasts to other subscribers.

---

## 4. Database Hardening & Storage (CONF-01, OPS-01)

### 4.1 SQLite File and Directory Permissions
- On POSIX operating systems:
  - Database parent directory (`backend/database/`): target permission `0700` (`drwx------`).
  - Database file (`backend/database/netwatch.db`): target permission `0600` (`-rw-------`).
- On Windows:
  - Access is governed by Windows NTFS Access Control Lists (ACLs).
  - The database file and directory must be restricted to the dedicated service account and local Administrators:
    ```powershell
    icacls "backend\database" /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "NetWatchServiceUser:(OI)(CI)F"
    ```

### 4.2 SQLite Pragmas & WAL Mode
Every database connection automatically executes:
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=10000;
```
This guarantees concurrency safety between the background sampling writer and concurrent read requests.

### 4.3 Database Backup & Recovery Procedure
**Never copy an active SQLite database directly while the application is running**, as WAL state can cause inconsistency or corruption.

- **Safe Online Backup Command:**
  Use the SQLite online backup API via sqlite3 CLI:
  ```bash
  # Linux
  sqlite3 backend/database/netwatch.db ".backup 'backend/database/netwatch_backup_$(date +%Y%m%d_%H%M%S).db'"

  # Windows PowerShell
  sqlite3.exe backend\database\netwatch.db ".backup 'backend\database\netwatch_backup.db'"
  ```
- **Restore Procedure:**
  1. Stop the NetWatch service.
  2. Replace `backend/database/netwatch.db` with the verified backup file.
  3. Remove any residual `-wal` and `-shm` files.
  4. Start the NetWatch service.

---

## 5. Linux Service Deployment (systemd)

### 5.1 Service Account Setup
Create a dedicated least-privilege system user:
```bash
sudo useradd -r -s /bin/false -d /opt/netwatch netwatch
sudo mkdir -p /opt/netwatch /var/log/netwatch
sudo chown -R netwatch:netwatch /opt/netwatch /var/log/netwatch
```

### 5.2 systemd Unit Configuration
Create `/etc/systemd/system/netwatch.service`:
```ini
[Unit]
Description=NetWatch AI Telemetry Monitoring Service
After=network.target

[Service]
Type=simple
User=netwatch
Group=netwatch
WorkingDirectory=/opt/netwatch
Environment="NETWATCH_ENV=production"
Environment="NETWATCH_API_KEY=your_secure_operator_key_here"
Environment="CORS_ORIGINS=https://netwatch.yourdomain.com"
Environment="DEVICE_SCAN_COOLDOWN_SECONDS=60"
Environment="WS_MAX_CLIENTS=20"
Environment="PYTHONPATH=."
ExecStart=/opt/netwatch/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=append:/var/log/netwatch/netwatch.log
StandardError=append:/var/log/netwatch/netwatch.err

# Security sandbox
ProtectSystem=full
ProtectHome=true
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable netwatch
sudo systemctl start netwatch
sudo systemctl status netwatch
```

---

## 6. Windows Service Deployment (NSSM)

### 6.1 Service Creation via NSSM
1. Download [NSSM (Non-Sucking Service Manager)](https://nssm.cc/).
2. Run PowerShell as Administrator:
   ```powershell
   # Install service
   nssm install NetWatchAI "C:\Users\navan\OneDrive\Desktop\NetWatch AI\venv\Scripts\python.exe" "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1"
   
   # Set working directory
   nssm set NetWatchAI AppDirectory "C:\Users\navan\OneDrive\Desktop\NetWatch AI"

   # Set environment variables
   nssm set NetWatchAI AppEnvironmentExtra NETWATCH_ENV=production^
NETWATCH_API_KEY=your_secure_operator_key^
CORS_ORIGINS=http://localhost:5173^
DEVICE_SCAN_COOLDOWN_SECONDS=60^
WS_MAX_CLIENTS=20^
PYTHONPATH=.

   # Output logging
   nssm set NetWatchAI AppStdout "C:\Users\navan\OneDrive\Desktop\NetWatch AI\backend\netwatch_service.log"
   nssm set NetWatchAI AppStderr "C:\Users\navan\OneDrive\Desktop\NetWatch AI\backend\netwatch_service_err.log"

   # Start service
   nssm start NetWatchAI
   ```

3. Verification:
   ```powershell
   Get-Service NetWatchAI
   curl.exe http://127.0.0.1:8000/api/health
   ```

---

## 7. Reverse Proxy & Transport Security (Nginx)

When exposing NetWatch to operator workstations, place it behind an SSL/TLS terminating reverse proxy. Never expose Uvicorn directly to the public internet.

```nginx
# /etc/nginx/sites-available/netwatch
server {
    listen 80;
    server_name netwatch.local;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name netwatch.local;

    ssl_certificate /etc/ssl/certs/netwatch.crt;
    ssl_certificate_key /etc/ssl/private/netwatch.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend static bundle
    location / {
        root /opt/netwatch/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }

    # WebSocket Proxy
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

---

## 8. Health Monitoring & Operational Troubleshooting

### 8.1 Health Endpoint Semantics (`/api/health`)
- **Liveness vs Readiness:**
  - Liveness: Checks whether the HTTP server process is running and responding to requests.
  - Readiness / Database Health: Performs a live `SELECT 1` against SQLite, measuring execution latency in milliseconds.
  - If the database is responsive: `status: "ok"`, `details.database: "ok"`, `details.db_latency_ms: <float>`.
  - If the database fails: `status: "degraded"`, `details.database: "degraded"`, `details.db_latency_ms: null`. Status code returns HTTP 200 with degraded indication so orchestrators do not needlessly enter restart death loops for transient file locks.

### 8.2 Operator Key Rotation
To rotate `NETWATCH_API_KEY`:
1. Generate a new high-entropy secret (e.g. `openssl rand -hex 32`).
2. Update the environment variable in the systemd unit or NSSM configuration.
3. Reload/restart the service (`systemctl restart netwatch` or `nssm restart NetWatchAI`).
4. Operators enter the new key into their browser session when performing manual scans or acknowledging alerts.

---

## 9. Verification & Pre-Deployment Checklist

Before deploying into service:
1. Verify backend tests pass:
   ```bash
   pytest backend/tests/test_phase13_security.py backend/tests/test_websocket_capacity.py backend/tests/test_phase13_reliability.py -v
   ```
2. Verify earlier phase regression suites pass:
   ```bash
   python backend/tests/test_phase8_exitgate.py
   python backend/tests/test_phase9_exitgate.py
   python backend/tests/test_phase10_exitgate.py
   python backend/tests/test_phase11_exitgate.py
   ```
3. Verify frontend production compilation succeeds with 0 errors:
   ```bash
   cd frontend && npm run build
   ```
4. Verify `/api/health` reports status `ok` and numeric `db_latency_ms`.
