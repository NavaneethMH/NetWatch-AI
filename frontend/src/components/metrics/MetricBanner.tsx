import React from 'react';
import { 
  TrendingDown, 
  TrendingUp, 
  Cpu, 
  Layers, 
  HardDrive, 
  Clock,
  Activity
} from 'lucide-react';
import type { SystemTelemetry, NetworkThroughput, LatencySnapshot } from '../../types/telemetry';
import { formatBytes, formatUptime } from '../../utils/formatters';

interface MetricBannerProps {
  system: SystemTelemetry | null;
  network: NetworkThroughput | null;
  latency: LatencySnapshot | null;
  isOffline: boolean;
}

export const MetricBanner: React.FC<MetricBannerProps> = ({
  system,
  network,
  latency,
  isOffline
}) => {
  return (
    <div className="noc-metric-banner">
      <div className="noc-banner-cell highlight-dl">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <TrendingDown size={14} className="color-dl" />
            <span>DOWNLOAD</span>
          </div>
          <span className="noc-cell-delta mono">
            {network?.sample_interval_seconds ? `Δt: ${network.sample_interval_seconds}s` : '—'}
          </span>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value mono color-dl">
            {isOffline ? '—' : network?.download_mbps !== null && network?.download_mbps !== undefined 
              ? network.download_mbps.toFixed(3) 
              : '—'}
          </span>
          <span className="noc-cell-unit">
            {isOffline ? 'OFFLINE' : network?.status === 'WARMING_UP' ? 'WARMING UP' : network?.status === 'RESET' ? 'RESET' : 'Mbps'}
          </span>
        </div>
        <div className="noc-cell-sub mono">
          {network ? formatBytes(network.bytes_recv_total) : '—'}
        </div>
      </div>

      <div className="noc-banner-cell highlight-ul">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <TrendingUp size={14} className="color-ul" />
            <span>UPLOAD</span>
          </div>
          <span className="noc-cell-delta mono">
            {network?.sample_interval_seconds ? `Δt: ${network.sample_interval_seconds}s` : '—'}
          </span>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value mono color-ul">
            {isOffline ? '—' : network?.upload_mbps !== null && network?.upload_mbps !== undefined 
              ? network.upload_mbps.toFixed(3) 
              : '—'}
          </span>
          <span className="noc-cell-unit">
            {isOffline ? 'OFFLINE' : network?.status === 'WARMING_UP' ? 'WARMING UP' : network?.status === 'RESET' ? 'RESET' : 'Mbps'}
          </span>
        </div>
        <div className="noc-cell-sub mono">
          {network ? formatBytes(network.bytes_sent_total) : '—'}
        </div>
      </div>

      <div className="noc-banner-cell">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <Activity size={14} color="#f43f5e" />
            <span>LATENCY</span>
          </div>
          <span className="noc-cell-sub-info mono">
            {latency?.target || '—'}
          </span>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value mono">
            {isOffline ? '—' : latency?.latency_last_ms !== null && latency?.latency_last_ms !== undefined 
              ? `${latency.latency_last_ms.toFixed(0)}` 
              : latency?.latency_avg_ms !== null && latency?.latency_avg_ms !== undefined
              ? `${latency.latency_avg_ms.toFixed(0)}`
              : '—'}
          </span>
          <span className="noc-cell-unit">
            {isOffline ? 'OFFLINE' : latency?.is_stale ? 'STALE' : latency?.status === 'WARMING_UP' ? 'WARMING UP' : latency?.status === 'UNREACHABLE' ? 'UNREACHABLE' : latency?.status === 'PARTIAL' ? 'PARTIAL' : latency?.status === 'ERROR' ? 'ERROR' : 'ms'}
          </span>
        </div>
        <div className="noc-cell-sub mono">
          {isOffline ? '—' : latency?.packet_loss_percent !== null && latency?.packet_loss_percent !== undefined 
            ? `Loss: ${latency.packet_loss_percent.toFixed(1)}%` 
            : 'Loss: —'}
          {latency?.probe_age_seconds !== null && latency?.probe_age_seconds !== undefined && !isOffline && (
            <span style={{ marginLeft: '6px', opacity: 0.75 }}>
              ({latency.probe_age_seconds.toFixed(0)}s ago)
            </span>
          )}
        </div>
      </div>

      <div className="noc-banner-cell">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <Cpu size={14} color="#a78bfa" />
            <span>CPU UTILIZATION</span>
          </div>
          <span className="noc-cell-sub-info">
            {system?.cpu.core_count_logical ? `${system.cpu.core_count_logical} Cores` : '—'}
          </span>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value mono">
            {isOffline ? '—' : system?.cpu.usage_percent !== null && system?.cpu.usage_percent !== undefined
              ? `${system.cpu.usage_percent}%`
              : '—'}
          </span>
          <span className="noc-cell-unit">
            {isOffline ? 'OFFLINE' : system?.cpu.is_ready ? 'LOAD' : 'PRIMING'}
          </span>
        </div>
        <div className="noc-mini-bar">
          <div 
            className="noc-mini-bar-fill" 
            style={{ 
              width: !isOffline && system?.cpu.usage_percent ? `${Math.min(100, Math.max(3, system.cpu.usage_percent))}%` : '0%',
              backgroundColor: '#a78bfa'
            }} 
          />
        </div>
      </div>

      <div className="noc-banner-cell">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <Layers size={14} color="#60a5fa" />
            <span>SYSTEM RAM</span>
          </div>
          <span className="noc-cell-sub-info mono">
            {system ? `${formatBytes(system.memory.used_bytes)} / ${formatBytes(system.memory.total_bytes)}` : '—'}
          </span>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value mono">
            {isOffline ? '—' : system ? `${system.memory.usage_percent}%` : '—'}
          </span>
          <span className="noc-cell-unit">USED</span>
        </div>
        <div className="noc-mini-bar">
          <div 
            className="noc-mini-bar-fill" 
            style={{ 
              width: !isOffline && system ? `${Math.min(100, Math.max(3, system.memory.usage_percent))}%` : '0%',
              backgroundColor: '#60a5fa'
            }} 
          />
        </div>
      </div>

      <div className="noc-banner-cell">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <HardDrive size={14} color="#34d399" />
            <span>DISK STORAGE</span>
          </div>
          <span className="noc-cell-sub-info mono">
            {system?.disk.mount_point || 'C:'}
          </span>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value mono">
            {isOffline ? '—' : system ? `${system.disk.usage_percent}%` : '—'}
          </span>
          <span className="noc-cell-unit">CAPACITY</span>
        </div>
        <div className="noc-mini-bar">
          <div 
            className="noc-mini-bar-fill" 
            style={{ 
              width: !isOffline && system ? `${Math.min(100, Math.max(3, system.disk.usage_percent))}%` : '0%',
              backgroundColor: '#34d399'
            }} 
          />
        </div>
      </div>

      <div className="noc-banner-cell">
        <div className="noc-cell-header">
          <div className="noc-cell-title">
            <Clock size={14} color="#fbbf24" />
            <span>HOST UPTIME</span>
          </div>
        </div>
        <div className="noc-cell-body">
          <span className="noc-cell-value-compact mono">
            {isOffline ? '—' : system ? formatUptime(system.system_uptime_seconds) : '—'}
          </span>
        </div>
        <div className="noc-cell-sub mono">
          Boot: {system ? new Date(system.boot_time_timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
        </div>
      </div>
    </div>
  );
};
