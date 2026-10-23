/**
 * NetWatch AI - Core Domain Types
 * Strongly matched to FastAPI Pydantic responses.
 */

export interface InterfaceAddress {
  family: string;
  address: string;
  netmask: string | null;
  broadcast: string | null;
}

export interface InterfaceInfo {
  name: string;
  is_up: boolean;
  speed_mbps: number | null;
  mtu: number | null;
  addresses: InterfaceAddress[];
}

export interface CpuMetrics {
  usage_percent: number | null;
  is_ready: boolean;
  core_count_logical: number | null;
  core_count_physical: number | null;
}

export interface MemoryMetrics {
  usage_percent: number;
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
}

export interface DiskMetrics {
  usage_percent: number;
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  mount_point: string;
}

export interface NetworkTotals {
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
  errin: number;
  errout: number;
  dropin: number;
  dropout: number;
}

export interface SystemTelemetry {
  timestamp: number;
  timestamp_iso: string;
  system_uptime_seconds: number;
  boot_time_timestamp: number;
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  network_totals: NetworkTotals;
  interfaces: InterfaceInfo[];
  collector_status: string;
  unavailable_fields: string[];
}

export interface InterfaceThroughput {
  name: string;
  is_up: boolean;
  download_mbps: number | null;
  upload_mbps: number | null;
  bytes_recv: number;
  bytes_sent: number;
  packets_recv: number;
  packets_sent: number;
}

export interface NetworkThroughput {
  timestamp: number;
  timestamp_iso: string;
  status: 'LIVE' | 'WARMING_UP' | 'RESET';
  download_mbps: number | null;
  upload_mbps: number | null;
  bytes_recv_total: number;
  bytes_sent_total: number;
  packets_recv_total: number;
  packets_sent_total: number;
  sample_interval_seconds: number | null;
  interfaces: InterfaceThroughput[];
}

export interface NetworkHistoryItem {
  id: number;
  sample_id: string;
  timestamp: number;
  timestamp_utc: string;
  status: string;
  download_mbps: number | null;
  upload_mbps: number | null;
  bytes_recv: number;
  bytes_sent: number;
  packets_recv: number;
  packets_sent: number;
  elapsed_seconds: number | null;
}

export interface SystemHistoryItem {
  id: number;
  sample_id: string;
  timestamp: number;
  timestamp_utc: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number | null;
  disk_percent: number | null;
  disk_used_bytes: number | null;
  disk_total_bytes: number | null;
  uptime_seconds: number | null;
  collector_status: string;
  unavailable_fields: string | null;
}

export interface LatencySnapshot {
  probe_id?: string;
  target: string;
  is_reachable: boolean;
  packets_sent?: number;
  packets_received?: number;
  packet_loss_percent: number | null;
  latency_last_ms?: number | null;
  latency_min_ms?: number | null;
  latency_max_ms?: number | null;
  latency_avg_ms?: number | null;
  current_latency_ms?: number | null;
  min_latency_ms?: number | null;
  max_latency_ms?: number | null;
  avg_latency_ms?: number | null;
  timestamp?: number;
  timestamp_utc?: string;
  probe_age_seconds?: number | null;
  is_stale?: boolean;
  status: 'LIVE' | 'PARTIAL' | 'UNREACHABLE' | 'ERROR' | 'WARMING_UP' | string;
}

export interface LatencyHistoryItem {
  id: number;
  probe_id: string;
  timestamp: number;
  timestamp_utc: string;
  target: string;
  status: string;
  is_reachable: boolean;
  packets_sent: number;
  packets_received: number;
  packet_loss_percent: number | null;
  latency_last_ms: number | null;
  latency_min_ms: number | null;
  latency_max_ms: number | null;
  latency_avg_ms: number | null;
}

export interface LatencyHistoryResponse {
  target: string | null;
  count: number;
  limit: number;
  items: LatencyHistoryItem[];
}

export interface ScoreDeduction {
  category: string;
  reason: string;
  points: number;
  observed_value?: string | null;
}

export interface HealthScoreData {
  score: number;
  status: 'HEALTHY' | 'DEGRADED' | 'POOR' | 'CRITICAL' | string;
  timestamp: number;
  timestamp_utc: string;
  deductions: ScoreDeduction[];
  telemetry_freshness?: Record<string, any>;
}

export interface AlertSummaryData {
  total_active: number;
  open_count: number;
  acknowledged_count: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
}

export interface AlertItemData {
  id: number;
  alert_id: string;
  type: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL' | string;
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | string;
  source: string;
  message: string;
  metric_name: string;
  observed_value: number | null;
  threshold_value: number | null;
  opened_at: number;
  opened_at_utc: string;
  acknowledged_at: number | null;
  acknowledged_at_utc: string | null;
  resolved_at: number | null;
  resolved_at_utc: string | null;
  last_seen_at: number;
  last_seen_at_utc: string;
  occurrence_count: number;
}

export interface WebSocketTelemetryMessage {
  type: 'snapshot' | 'telemetry';
  sample_id: string;
  timestamp_utc: string;
  system: SystemTelemetry;
  network: NetworkThroughput;
  latency?: LatencySnapshot;
  health_score?: HealthScoreData;
  alerts_summary?: AlertSummaryData;
  devices?: DeviceSummary;
  connections?: ConnectionSummary;
  protocols?: ProtocolSummary;
}


export type ConnectionState = 'CONNECTING' | 'LIVE' | 'DELAYED' | 'OFFLINE';

export interface ChartDataPoint {
  time: string;
  timestamp: number;
  download: number | null;
  upload: number | null;
  status: string;
}

export type ActivePage = 'overview' | 'network' | 'interfaces' | 'history' | 'devices' | 'alerts' | 'connections' | 'protocols' | 'insights';

// ─── Phase 9: Device Discovery Types ────────────────────────────────────────

export interface DeviceItem {
  id: number;
  mac_address: string | null;
  ip_address: string;
  hostname: string | null;
  interface_name: string;
  first_seen: number;
  first_seen_utc: string;
  last_seen: number;
  last_seen_utc: string;
  status: 'ONLINE' | 'OFFLINE' | 'UNKNOWN' | string;
  missed_scan_count: number;
}

export interface DeviceListResponse {
  count: number;
  total: number;
  items: DeviceItem[];
}

export interface DiscoveryStatus {
  status: 'IDLE' | 'SCANNING' | 'ERROR' | 'UNAVAILABLE' | string;
  discovery_method: string;
  interface: string | null;
  subnet: string | null;
  last_scan_utc: string | null;
  last_scan_duration_seconds: number | null;
  devices_found_last_scan: number | null;
  limitation: string | null;
  error: string | null;
}

export interface DeviceSummary {
  online: number;
  known: number;
  discovery_status: string;
  last_scan_utc: string | null;
}

// ─── Phase 10: Active Connection Monitoring Types ────────────────────────────

export interface ConnectionItem {
  id: string;
  protocol: string;
  local_ip: string | null;
  local_port: number | null;
  remote_ip: string | null;
  remote_port: number | null;
  state: string;
  family: string;
  pid: number | null;
  process_name: string | null;
  first_observed: number;
  first_observed_utc: string;
  last_observed: number;
  last_observed_utc: string;
}

export interface ConnectionListResponse {
  count: number;
  total: number;
  items: ConnectionItem[];
}

export interface ConnectionSummary {
  total: number;
  tcp: number;
  udp: number;
  established: number;
  listening: number;
  time_wait: number;
  close_wait: number;
  other: number;
  last_scan_utc: string | null;
  scan_duration_ms: number | null;
}

// ─── Phase 11: Real Packet & Protocol Analytics Types ────────────────────────

export interface ProtocolWindowMetric {
  window_id: string;
  timestamp: number;
  timestamp_utc: string;
  interface: string | null;
  status: 'LIVE' | 'WARMING_UP' | 'PERMISSION_REQUIRED' | 'INTERFACE_UNAVAILABLE' | 'ERROR' | 'STOPPED' | string;
  window_duration_seconds: number;
  total_packets: number;
  total_bytes: number;
  packets_per_second: number;
  bytes_per_second: number;
  avg_packet_size: number;
  tcp_packets: number;
  udp_packets: number;
  icmp_packets: number;
  other_transport_packets: number;
  dns_packets: number;
  ipv4_packets: number;
  ipv6_packets: number;
  other_network_packets: number;
  non_ip_packets?: number;
  error_message: string | null;
}

export interface ProtocolHistoryResponse {
  count: number;
  total: number;
  items: ProtocolWindowMetric[];
}

export interface ProtocolSummary {
  status: string;
  interface: string | null;
  pps: number;
  bps: number;
  total_packets: number;
  tcp: number;
  udp: number;
  icmp: number;
  dns: number;
  other: number;
  ipv4: number;
  ipv6: number;
  avg_packet_size: number;
  last_window_utc: string | null;
  limitation_reason: string | null;
}


// --- Phase 12: Historical Analytics & Reporting Types ---

export interface TableCoverage {
  table: string;
  row_count: number;
  oldest_ts: number | null;
  newest_ts: number | null;
  oldest_utc: string | null;
  newest_utc: string | null;
  span_seconds: number | null;
  span_human: string | null;
  retention_seconds: number | null;
  retention_human: string | null;
}

export interface AnalyticsCoverage {
  generated_at_utc: string;
  tables: TableCoverage[];
}

export interface TimeSeriesPoint {
  bucket_ts: number;
  bucket_utc: string;
  download_mbps: number | null;
  upload_mbps: number | null;
  cpu_percent: number | null;
  memory_percent: number | null;
  latency_avg_ms: number | null;
  latency_min_ms: number | null;
  latency_max_ms: number | null;
  packet_loss_percent: number | null;
  pps: number | null;
  total_packets: number | null;
  tcp_packets: number | null;
  udp_packets: number | null;
  icmp_packets: number | null;
  dns_packets: number | null;
  ipv4_packets: number | null;
  ipv6_packets: number | null;
}

export interface TimeSeriesResponse {
  from_ts: number;
  to_ts: number;
  from_utc: string;
  to_utc: string;
  bucket_seconds: number;
  point_count: number;
  metrics: string[];
  points: TimeSeriesPoint[];
}

export interface MetricAggregate {
  min: number | null;
  max: number | null;
  avg: number | null;
  p95: number | null;
  sample_count: number;
}

export interface AnalyticsReport {
  from_ts: number;
  to_ts: number;
  from_utc: string;
  to_utc: string;
  window_seconds: number;
  window_human: string;
  download_mbps: MetricAggregate;
  upload_mbps: MetricAggregate;
  cpu_percent: MetricAggregate;
  memory_percent: MetricAggregate;
  latency_avg_ms: MetricAggregate;
  packet_loss_percent: MetricAggregate;
  pps: MetricAggregate;
  total_packets: number;
  tcp_share_pct: number | null;
  udp_share_pct: number | null;
  icmp_share_pct: number | null;
  dns_share_pct: number | null;
  ipv4_share_pct: number | null;
  ipv6_share_pct: number | null;
  total_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  info_alerts: number;
}