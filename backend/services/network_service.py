"""Network Telemetry Service Layer"""
from backend.collectors.network import network_collector, NetworkCollector
from backend.schemas.network import NetworkThroughputResponse

class NetworkService:
    def __init__(self, collector: NetworkCollector = network_collector):
        self.collector = collector

    def get_current_network_throughput(self) -> NetworkThroughputResponse:
        """Fetch real-time network throughput and interface deltas."""
        return self.collector.collect()

network_service = NetworkService()
