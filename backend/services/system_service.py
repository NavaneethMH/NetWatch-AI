"""System Telemetry Service Layer"""
from backend.collectors.system import system_collector, SystemCollector
from backend.schemas.system import SystemTelemetryResponse

class SystemService:
    def __init__(self, collector: SystemCollector = system_collector):
        self.collector = collector

    def get_current_system_telemetry(self) -> SystemTelemetryResponse:
        """Fetch real system and interface telemetry from collector."""
        return self.collector.collect()

system_service = SystemService()
