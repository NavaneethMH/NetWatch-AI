"""Health Check Router — includes live SQLite liveness probe (Phase 13.2)"""
from fastapi import APIRouter
import time
import logging
from backend.core.config import settings
from backend.schemas.health import HealthResponse

router = APIRouter()
logger = logging.getLogger("netwatch.api.health")

_START_TIME = time.time()


def _probe_database() -> tuple[str, float | None]:
    """Execute SELECT 1 against the SQLite engine; return (status, latency_ms).

    Returns:
        ("ok", latency_ms)        — DB responded within 5 s.
        ("degraded", None)        — DB raised an exception or timed out.
    """
    try:
        from backend.database.session import engine
        t0 = time.perf_counter()
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return "ok", latency_ms
    except Exception as exc:
        logger.warning("Health DB probe failed: %s", exc)
        return "degraded", None


@router.get("/health", response_model=HealthResponse)
def get_health():
    uptime_seconds = round(time.time() - _START_TIME, 2)
    db_status, db_latency_ms = _probe_database()

    overall_status = "ok" if db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.VERSION,
        telemetry_status="LIVE",
        details={
            "app": settings.PROJECT_NAME,
            "uptime_seconds": uptime_seconds,
            "database": db_status,
            "db_latency_ms": db_latency_ms,
            "telemetry_engine": "operational",
            "environment": settings.ENVIRONMENT,
            "scan_cooldown_seconds": settings.DEVICE_SCAN_COOLDOWN_SECONDS,
        }
    )
