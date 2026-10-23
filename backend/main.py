"""NetWatch AI Backend Entrypoint with Lifespan Management and Worker Enforcement"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import os
import sys

from backend.core.config import settings
from backend.api.health import router as health_router
from backend.api.system import router as system_router
from backend.api.network import router as network_router
from backend.api.latency import router as latency_router
from backend.api.alerts import router as alerts_router
from backend.api.health_score import router as health_score_router
from backend.api.websocket import router as websocket_router
from backend.api.devices import router as devices_router
from backend.api.connections import router as connections_router
from backend.api.protocols import router as protocols_router
from backend.api.analytics import router as analytics_router
from backend.services.storage_service import storage_worker
from backend.collectors.latency import latency_collector
from backend.collectors.device_discovery import device_discovery
from backend.collectors.connections import connection_collector
from backend.collectors.packets import packet_collector
from backend.services.device_service import device_service  # noqa: F401 – registers callback
from backend.services.connection_service import connection_service  # noqa: F401 – registers callback
from backend.services.protocol_service import protocol_service  # noqa: F401 – registers callback
from backend.services.broadcaster import broadcaster

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("netwatch.main")

# ==============================================================================
# SINGLE-WORKER ENFORCEMENT & ARCHITECTURE SPECIFICATION
#
# NetWatch AI utilizes an in-process, stateful telemetry engine:
# 1. Monotonic elapsed-time delta counters require state continuity within the process.
# 2. Background autonomous SQLite persistence runs once every SAMPLING_INTERVAL_SECONDS.
# 3. Running multi-worker Uvicorn (e.g. `uvicorn --workers 4`) is UNSUPPORTED because:
#    - Multiple independent sampling threads will produce interleaved, overlapping database ticks.
#    - High-frequency delta resets across processes produce erratic Mbps readings.
#
# NetWatch is designed to scale horizontally by deploying separate instances per host,
# NOT by spawning multiple workers on the same machine.
# ==============================================================================
PID_FILE = os.path.join(os.path.dirname(__file__), "netwatch.pid")

def check_single_worker_environment():
    """Detects active competing workers while safely handling stale PID files from crashes."""
    current_pid = os.getpid()
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                content = f.read().strip()
                existing_pid = int(content) if content else None

            if existing_pid and existing_pid != current_pid:
                import psutil
                if psutil.pid_exists(existing_pid):
                    # Check if process is still running Python/Uvicorn or is an unrelated recycled PID
                    try:
                        proc = psutil.Process(existing_pid)
                        cmdline = " ".join(proc.cmdline())
                        if "uvicorn" in cmdline.lower() or "python" in cmdline.lower():
                            logger.warning(
                                f"⚠️ MULTI-WORKER DETECTED! Another active NetWatch process (PID {existing_pid}) is running. "
                                f"NetWatch strictly requires a SINGLE worker process. Multi-worker Uvicorn configurations "
                                f"cause overlapping ticks, lock contention, and counter desynchronization."
                            )
                        else:
                            # Stale PID: process exists but is an unrelated application that reused the OS PID
                            logger.info(f"Overwriting stale PID file (PID {existing_pid} is no longer NetWatch).")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        logger.info(f"Overwriting stale PID file (PID {existing_pid} does not exist).")
                else:
                    # Dead process
                    logger.info(f"Cleaned up stale PID file from previously terminated PID {existing_pid}.")
        except Exception as e:
            logger.debug(f"PID check exception (safely continuing): {e}")

    try:
        with open(PID_FILE, "w") as f:
            f.write(str(current_pid))
    except Exception as e:
        logger.warning(f"Could not write PID file: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enforce single worker check with stale PID protection
    check_single_worker_environment()

    # Capture asyncio event loop for thread-safe WebSocket broadcast
    loop = asyncio.get_running_loop()
    broadcaster.set_loop(loop)

    # Startup: Start autonomous background workers
    logger.info("Starting NetWatch autonomous storage and telemetry worker...")
    storage_worker.start()
    logger.info("Starting NetWatch latency probe collector...")
    latency_collector.start()
    logger.info("Starting NetWatch LAN device discovery worker...")
    device_discovery.start()
    logger.info("Starting NetWatch host active connection collector...")
    connection_collector.start()
    logger.info("Starting NetWatch packet and protocol analytics collector...")
    packet_collector.start()

    yield

    # Shutdown: Cleanly stop all background workers then remove pid file
    logger.info("Stopping NetWatch background workers...")
    packet_collector.stop()
    connection_collector.stop()
    device_discovery.stop()
    storage_worker.stop()
    latency_collector.stop()
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Real-time Network Telemetry and Anomaly Monitoring System",
    lifespan=lifespan
)

# CORS setup with explicit allowed origins, methods, and headers (Phase 13.1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization", "X-NetWatch-Key"],
)

# Mount API routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(system_router, prefix="/api", tags=["System Telemetry"])
app.include_router(network_router, prefix="/api", tags=["Network Telemetry"])
app.include_router(latency_router, prefix="/api", tags=["Latency Monitoring"])
app.include_router(alerts_router, prefix="/api", tags=["Alerts Engine"])
app.include_router(health_score_router, prefix="/api", tags=["Network Health Score"])
app.include_router(devices_router, prefix="/api", tags=["Device Discovery"])
app.include_router(connections_router, prefix="/api", tags=["Active Connections"])
app.include_router(protocols_router, prefix="/api", tags=["Protocol Analytics"])
app.include_router(analytics_router, prefix="/api", tags=["Historical Analytics"])
app.include_router(websocket_router, tags=["WebSocket Telemetry"])

if __name__ == "__main__":
    import uvicorn
    # Single worker strictly enforced: workers=1
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True, workers=1)
