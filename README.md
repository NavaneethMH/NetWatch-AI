# NetWatch AI

**Real-Time Single-Host Network Operations Center (NOC) & Observability Dashboard**

NetWatch AI is a production-conscious, low-overhead network monitoring system engineered for high-fidelity single-host telemetry, active connection auditing, LAN device discovery, and protocol rate analytics.

---

## Key Features

- **Live System & Throughput Telemetry:** Real-time host bandwidth, CPU, memory, drive metrics, and hardware adapter counters via psutil.
- **Autonomous Deterministic Latency:** Periodic non-blocking ICMP/UDP probes tracking reachability, packet loss, and jitter.
- **Real Active Connection Inspector:** Dynamic socket state mapping (TCP/UDP, IPv4/IPv6, process names, PIDs) using host socket tables without remote port scanning.
- **LAN Device Discovery:** Zero-privilege ARP table inspection and targeted subnet ICMP sweeping with MAC deduplication.
- **Packet & Protocol Analytics:** Lightweight Layer-3/4 packet metadata inspection (TCP, UDP, ICMP, DNS subsets) using Scapy (Npcap-supported) without storing payload contents.
- **Alert State Machine & Health Scoring:** Deterministic severity levels (`INFO`, `WARNING`, `CRITICAL`), deduplication windows, and composite network health calculations.
- **Autonomous SQLite WAL Persistence:** High-performance write-ahead logging with bounded retention and fast recovery.
- **Production-Hardened Security:** Fail-closed production mode, operator key authentication (`X-NetWatch-Key`), single-worker PID locks, rate-limiting cooldowns, and strict CORS.

---

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy, SQLite (WAL mode), psutil, Scapy.
- **Frontend:** React 19, TypeScript, Vite, Recharts, Lucide Icons, Vanilla CSS (Geist & JetBrains Mono typography).

---

## Getting Started

### Quick Start (Windows)
Double-click [`start_servers.bat`](file:///c:/Users/navan/OneDrive/Desktop/NetWatch%20AI/start_servers.bat) or run:
```cmd
start_servers.bat
```
This automatically boots both the FastAPI backend and Vite frontend dev servers in dedicated windows.

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- *(Optional on Windows)* [Npcap](https://npcap.com/) for raw packet capture.

### 2. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run backend server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## Operational Configuration

Environment variables can be set directly or via deployment scripts:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `NETWATCH_ENV` | `development` | Set to `production` to enforce strict security and fail-closed checks. |
| `NETWATCH_API_KEY` | *(dev fallback)* | Required secret key for privileged actions (manual LAN scans, acknowledging alerts). |
| `NETWATCH_CORS_ORIGINS` | `http://127.0.0.1:8000,http://localhost:8000` | Comma-separated list of allowed origins. Wildcards (`*`) are disallowed in production. |

---

## License

MIT License. Designed and engineered for high-reliability network observability.
