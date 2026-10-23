import React from 'react';
import type { LatencySnapshot } from '../../types/telemetry';
import { Activity, ShieldCheck, AlertTriangle, XCircle, Clock } from 'lucide-react';

interface NetworkQualitySectionProps {
  latency: LatencySnapshot | null;
  isOffline: boolean;
}

export const NetworkQualitySection: React.FC<NetworkQualitySectionProps> = ({
  latency,
  isOffline
}) => {
  const getStatusBadge = () => {
    if (isOffline) {
      return (
        <span className="noc-status-badge badge-offline">
          <XCircle size={12} /> OFFLINE
        </span>
      );
    }
    if (latency?.is_stale) {
      return (
        <span className="noc-status-badge badge-stale" style={{ backgroundColor: 'rgba(234, 179, 8, 0.15)', color: '#eab308' }}>
          <AlertTriangle size={12} /> STALE
        </span>
      );
    }
    switch (latency?.status) {
      case 'LIVE':
        return (
          <span className="noc-status-badge badge-live">
            <ShieldCheck size={12} /> LIVE (100% REACHABLE)
          </span>
        );
      case 'PARTIAL':
        return (
          <span className="noc-status-badge badge-delayed" style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
            <AlertTriangle size={12} /> PARTIAL LOSS
          </span>
        );
      case 'UNREACHABLE':
        return (
          <span className="noc-status-badge badge-offline" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>
            <XCircle size={12} /> UNREACHABLE
          </span>
        );
      case 'ERROR':
        return (
          <span className="noc-status-badge badge-offline" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>
            <AlertTriangle size={12} /> PROBE ERROR
          </span>
        );
      default:
        return (
          <span className="noc-status-badge badge-connecting">
            <Clock size={12} /> INITIALIZING
          </span>
        );
    }
  };

  const probeTimeStr = latency?.timestamp && latency.timestamp > 0 
    ? new Date(latency.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—';

  return (
    <div className="noc-card" style={{ marginBottom: '24px' }}>
      <div className="noc-card-header">
        <div className="noc-card-title">
          <Activity size={16} color="#f43f5e" />
          <span>NETWORK QUALITY & REAL PROBES</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {getStatusBadge()}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '16px', marginTop: '8px' }}>
        <div>
          <div className="noc-table-cell-sub">PROBE TARGET</div>
          <div className="mono" style={{ fontSize: '15px', fontWeight: 600, color: 'var(--noc-text-primary, #f1f5f9)', marginTop: '4px' }}>
            {latency?.target || '—'}
          </div>
        </div>

        <div>
          <div className="noc-table-cell-sub">REACHABILITY</div>
          <div className="mono" style={{ fontSize: '15px', fontWeight: 600, marginTop: '4px', color: latency?.is_reachable ? '#10b981' : '#ef4444' }}>
            {isOffline ? 'OFFLINE' : latency ? (latency.is_reachable ? 'REACHABLE' : 'UNREACHABLE') : '—'}
          </div>
        </div>

        <div>
          <div className="noc-table-cell-sub">AVERAGE LATENCY</div>
          <div className="mono" style={{ fontSize: '15px', fontWeight: 600, color: '#f43f5e', marginTop: '4px' }}>
            {isOffline || latency?.latency_avg_ms === null || latency?.latency_avg_ms === undefined 
              ? '—' 
              : `${latency.latency_avg_ms.toFixed(1)} ms`}
          </div>
        </div>

        <div>
          <div className="noc-table-cell-sub">MIN / MAX LATENCY</div>
          <div className="mono" style={{ fontSize: '15px', fontWeight: 600, color: 'var(--noc-text-primary, #f1f5f9)', marginTop: '4px' }}>
            {isOffline || latency?.latency_min_ms === null || latency?.latency_min_ms === undefined || latency?.latency_max_ms === null || latency?.latency_max_ms === undefined
              ? '—'
              : `${latency.latency_min_ms.toFixed(0)} ms / ${latency.latency_max_ms.toFixed(0)} ms`}
          </div>
        </div>

        <div>
          <div className="noc-table-cell-sub">PACKET LOSS</div>
          <div className="mono" style={{ fontSize: '15px', fontWeight: 600, marginTop: '4px', color: latency?.packet_loss_percent === 0 ? '#10b981' : latency?.packet_loss_percent ? '#ef4444' : 'inherit' }}>
            {isOffline || latency?.packet_loss_percent === null || latency?.packet_loss_percent === undefined
              ? '—'
              : `${latency.packet_loss_percent.toFixed(1)}%`}
          </div>
        </div>

        <div>
          <div className="noc-table-cell-sub">LAST PROBE TIME</div>
          <div className="mono" style={{ fontSize: '14px', color: 'var(--noc-text-secondary, #94a3b8)', marginTop: '4px' }}>
            {probeTimeStr}
            {latency?.probe_age_seconds !== null && latency?.probe_age_seconds !== undefined && !isOffline && (
              <span style={{ marginLeft: '4px', fontSize: '12px' }}>
                ({latency.probe_age_seconds.toFixed(0)}s ago)
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
