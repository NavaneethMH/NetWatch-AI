"""NetWatch AI Core Configuration"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    PROJECT_NAME: str = "NetWatch AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    SQLITE_URL: str = f"sqlite:///{BASE_DIR}/database/netwatch.db"
    
    # Telemetry sampling & persistence configuration
    SAMPLING_INTERVAL_SECONDS: float = 2.0  # Background tick rate
    TELEMETRY_RETENTION_DAYS: int = 7       # Configurable retention threshold
    CLEANUP_INTERVAL_SECONDS: float = 3600.0 # Retention pruning interval (1 hour)

    # Latency/Ping configuration (Phase 7)
    PING_TARGET: str = os.getenv("PING_TARGET", "1.1.1.1")
    PING_INTERVAL_SECONDS: int = int(os.getenv("PING_INTERVAL_SECONDS", "5"))
    PING_COUNT: int = int(os.getenv("PING_COUNT", "4"))

    # Alert Thresholds & Consecutive-Sample Configuration (Phase 8)
    ALERT_CPU_WARNING: float = float(os.getenv("ALERT_CPU_WARNING", "80.0"))
    ALERT_CPU_CRITICAL: float = float(os.getenv("ALERT_CPU_CRITICAL", "95.0"))

    ALERT_MEMORY_WARNING: float = float(os.getenv("ALERT_MEMORY_WARNING", "80.0"))
    ALERT_MEMORY_CRITICAL: float = float(os.getenv("ALERT_MEMORY_CRITICAL", "95.0"))

    ALERT_DISK_WARNING: float = float(os.getenv("ALERT_DISK_WARNING", "85.0"))
    ALERT_DISK_CRITICAL: float = float(os.getenv("ALERT_DISK_CRITICAL", "95.0"))

    ALERT_LATENCY_WARNING_MS: float = float(os.getenv("ALERT_LATENCY_WARNING_MS", "100.0"))
    ALERT_LATENCY_CRITICAL_MS: float = float(os.getenv("ALERT_LATENCY_CRITICAL_MS", "250.0"))

    ALERT_PACKET_LOSS_WARNING: float = float(os.getenv("ALERT_PACKET_LOSS_WARNING", "5.0"))
    ALERT_PACKET_LOSS_CRITICAL: float = float(os.getenv("ALERT_PACKET_LOSS_CRITICAL", "20.0"))

    # Consecutive sample protection
    ALERT_CONSECUTIVE_SAMPLES: int = int(os.getenv("ALERT_CONSECUTIVE_SAMPLES", "3"))
    ALERT_RESOLVE_CONSECUTIVE_SAMPLES: int = int(os.getenv("ALERT_RESOLVE_CONSECUTIVE_SAMPLES", "2"))

    # Device discovery configuration (Phase 9)
    DEVICE_DISCOVERY_INTERVAL_SECONDS: int = int(os.getenv("DEVICE_DISCOVERY_INTERVAL_SECONDS", "60"))
    DEVICE_OFFLINE_AFTER_MISSED_SCANS: int = int(os.getenv("DEVICE_OFFLINE_AFTER_MISSED_SCANS", "3"))
    # Max subnet host count allowed for automatic discovery. Subnets with more hosts require explicit config.
    DEVICE_MAX_AUTO_SCAN_HOSTS: int = int(os.getenv("DEVICE_MAX_AUTO_SCAN_HOSTS", "512"))
    # Timeout in ms per ICMP ping during sweep
    DEVICE_PING_SWEEP_TIMEOUT_MS: int = int(os.getenv("DEVICE_PING_SWEEP_TIMEOUT_MS", "500"))
    # Max concurrent ping workers in the sweep thread pool
    DEVICE_PING_SWEEP_WORKERS: int = int(os.getenv("DEVICE_PING_SWEEP_WORKERS", "32"))
    # Minimum seconds between operator-triggered manual scans (rate-limit cooldown)
    DEVICE_SCAN_COOLDOWN_SECONDS: int = int(os.getenv("DEVICE_SCAN_COOLDOWN_SECONDS", "60"))

    # Active Connections configuration (Phase 10)
    CONNECTION_SCAN_INTERVAL_SECONDS: float = float(os.getenv("CONNECTION_SCAN_INTERVAL_SECONDS", "5.0"))

    # Security & Hardening configuration (Phase 13.1)
    ENVIRONMENT: str = "development"
    API_KEY: str = ""
    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    WS_MAX_CLIENTS: int = 20

    def __init__(self):
        self.PING_TARGET = os.getenv("PING_TARGET", "1.1.1.1")
        self.PING_INTERVAL_SECONDS = int(os.getenv("PING_INTERVAL_SECONDS", "5"))
        self.PING_COUNT = int(os.getenv("PING_COUNT", "4"))

        self.ALERT_CPU_WARNING = float(os.getenv("ALERT_CPU_WARNING", "80.0"))
        self.ALERT_CPU_CRITICAL = float(os.getenv("ALERT_CPU_CRITICAL", "95.0"))
        self.ALERT_MEMORY_WARNING = float(os.getenv("ALERT_MEMORY_WARNING", "80.0"))
        self.ALERT_MEMORY_CRITICAL = float(os.getenv("ALERT_MEMORY_CRITICAL", "95.0"))
        self.ALERT_DISK_WARNING = float(os.getenv("ALERT_DISK_WARNING", "85.0"))
        self.ALERT_DISK_CRITICAL = float(os.getenv("ALERT_DISK_CRITICAL", "95.0"))
        self.ALERT_LATENCY_WARNING_MS = float(os.getenv("ALERT_LATENCY_WARNING_MS", "100.0"))
        self.ALERT_LATENCY_CRITICAL_MS = float(os.getenv("ALERT_LATENCY_CRITICAL_MS", "250.0"))
        self.ALERT_PACKET_LOSS_WARNING = float(os.getenv("ALERT_PACKET_LOSS_WARNING", "5.0"))
        self.ALERT_PACKET_LOSS_CRITICAL = float(os.getenv("ALERT_PACKET_LOSS_CRITICAL", "20.0"))

        self.ALERT_CONSECUTIVE_SAMPLES = int(os.getenv("ALERT_CONSECUTIVE_SAMPLES", "3"))
        self.ALERT_RESOLVE_CONSECUTIVE_SAMPLES = int(os.getenv("ALERT_RESOLVE_CONSECUTIVE_SAMPLES", "2"))

        self.DEVICE_DISCOVERY_INTERVAL_SECONDS = int(os.getenv("DEVICE_DISCOVERY_INTERVAL_SECONDS", "60"))
        self.DEVICE_OFFLINE_AFTER_MISSED_SCANS = int(os.getenv("DEVICE_OFFLINE_AFTER_MISSED_SCANS", "3"))
        self.DEVICE_MAX_AUTO_SCAN_HOSTS = int(os.getenv("DEVICE_MAX_AUTO_SCAN_HOSTS", "512"))
        self.DEVICE_PING_SWEEP_TIMEOUT_MS = int(os.getenv("DEVICE_PING_SWEEP_TIMEOUT_MS", "500"))
        self.DEVICE_PING_SWEEP_WORKERS = int(os.getenv("DEVICE_PING_SWEEP_WORKERS", "32"))
        self.DEVICE_SCAN_COOLDOWN_SECONDS = int(os.getenv("DEVICE_SCAN_COOLDOWN_SECONDS", "60"))

        self.CONNECTION_SCAN_INTERVAL_SECONDS = float(os.getenv("CONNECTION_SCAN_INTERVAL_SECONDS", "5.0"))

        self.ENVIRONMENT = os.getenv("NETWATCH_ENV", "development").lower()
        self.API_KEY = os.getenv("NETWATCH_API_KEY", "")

        cors_raw = os.getenv("CORS_ORIGINS", "")
        if cors_raw.strip():
            self.CORS_ORIGINS = [orig.strip() for orig in cors_raw.split(",") if orig.strip()]
        else:
            self.CORS_ORIGINS = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]

        self.WS_MAX_CLIENTS = int(os.getenv("WS_MAX_CLIENTS", "20"))

settings = Settings()
