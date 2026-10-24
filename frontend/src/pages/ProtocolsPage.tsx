import React, { useState, useEffect, useCallback } from 'react';
import { apiUrl } from '../utils/api';
import { 
  Activity, 
  RefreshCw, 
  AlertTriangle, 
  ShieldCheck, 
  Layers, 
  PieChart
} from 'lucide-react';
import type { 
  ProtocolSummary, 
  ProtocolWindowMetric, 
  ProtocolHistoryResponse 
} from '../types/telemetry';
import '../devices.css';
import '../connections.css';
import '../protocols.css';

interface ProtocolsPageProps {
  protocolSummary?: ProtocolSummary | null;
}

export const ProtocolsPage: React.FC<ProtocolsPageProps> = ({ protocolSummary }) => {
  const [currentMetric, setCurrentMetric] = useState<ProtocolWindowMetric | null>(null);
  const [history, setHistory] = useState<ProtocolWindowMetric[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProtocolData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [curRes, histRes] = await Promise.all([
        fetch(apiUrl('/api/protocols/current')),
        fetch(apiUrl('/api/protocols/history?limit=30'))
      ]);

      if (curRes.ok) {
        const cur: ProtocolWindowMetric = await curRes.json();
        setCurrentMetric(cur);
      }
      if (histRes.ok) {
        const hist: ProtocolHistoryResponse = await histRes.json();
        setHistory(hist.items);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch protocol statistics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProtocolData();
  }, [fetchProtocolData]);

  // Periodic refresh every 4 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      fetchProtocolData();
    }, 4000);
    return () => clearInterval(timer);
  }, [fetchProtocolData]);

  const activeStatus = protocolSummary?.status || currentMetric?.status || 'WARMING_UP';
  const isLive = activeStatus === 'LIVE';
  const isPermRequired = activeStatus === 'PERMISSION_REQUIRED';

  // Transport distribution (Mutually exclusive: TCP + UDP + ICMP + Other = 100%)
  const totalTransport = (currentMetric?.total_packets ?? 0);
  const tcpPct = totalTransport > 0 ? ((currentMetric?.tcp_packets ?? 0) / totalTransport) * 100 : 0;
  const udpPct = totalTransport > 0 ? ((currentMetric?.udp_packets ?? 0) / totalTransport) * 100 : 0;
  const icmpPct = totalTransport > 0 ? ((currentMetric?.icmp_packets ?? 0) / totalTransport) * 100 : 0;
  const otherPct = totalTransport > 0 ? ((currentMetric?.other_transport_packets ?? 0) / totalTransport) * 100 : 0;

  // Network layer breakdown
  const ipv4Count = currentMetric?.ipv4_packets ?? 0;
  const ipv6Count = currentMetric?.ipv6_packets ?? 0;
  const otherNetCount = currentMetric?.other_network_packets ?? 0;
  const totalNet = ipv4Count + ipv6Count + otherNetCount;
  const ipv4Pct = totalNet > 0 ? (ipv4Count / totalNet) * 100 : 0;
  const ipv6Pct = totalNet > 0 ? (ipv6Count / totalNet) * 100 : 0;

  return (
    <div className="page-container">
      {/* 1. Header */}
      <div className="page-header">
        <div className="page-header__left">
          <Activity size={22} className="page-icon" />
          <div>
            <h1 className="page-title">Packet & Protocol Analytics</h1>
            <p className="page-subtitle">
              Real-time Layer-3/4 packet metadata inspection and rate analytics (Phase 11)
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={() => fetchProtocolData()}
            className="devices-btn devices-btn--secondary"
            title="Refresh protocol analytics"
            disabled={loading}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error banner if fetch fails */}
      {error && (
        <div style={{ padding: '10px 14px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-critical)', borderRadius: '6px', color: 'var(--status-critical)', fontSize: '12px' }}>
          {error}
        </div>
      )}

      {/* 2. Permission Banner if degraded */}
      {isPermRequired && (
        <div className="perm-warning-banner">
          <AlertTriangle size={20} className="perm-warning-icon" />
          <div>
            <h4 className="perm-warning-title">Driver / Administrator Permissions Required for Raw Capture</h4>
            <p className="perm-warning-text">
              Windows raw socket packet capture requires Administrator elevation or the standard Npcap packet capture driver.
              To enable live wire inspection, launch the backend terminal as Administrator or install Npcap with WinPcap compatibility.
              All other NetWatch operations (throughput, interfaces, latency, alerts, LAN discovery, and active connections) remain 100% active.
            </p>
          </div>
        </div>
      )}

      {/* 3. KPI Bar */}
      <div className="conn-kpi-bar">
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Capture Status</span>
          <span className="conn-kpi-val mono" style={{ fontSize: '15px', color: isLive ? 'var(--status-live)' : 'var(--status-warning)' }}>
            {activeStatus}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Packet Rate</span>
          <span className="conn-kpi-val mono" style={{ color: 'var(--accent-cyan)' }}>
            {isLive ? `${currentMetric?.packets_per_second ?? 0} pps` : '—'}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Throughput</span>
          <span className="conn-kpi-val mono">
            {isLive ? `${Math.round(((currentMetric?.bytes_per_second ?? 0) * 8) / 1000)} kbps` : '—'}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Avg Packet Size</span>
          <span className="conn-kpi-val mono" style={{ fontSize: '15px' }}>
            {isLive ? `${currentMetric?.avg_packet_size ?? 0} B` : '—'}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Active Interface</span>
          <span className="conn-kpi-val mono" style={{ fontSize: '14px', color: '#60a5fa' }}>
            {protocolSummary?.interface || currentMetric?.interface || 'Wi-Fi'}
          </span>
        </div>
      </div>

      {/* 4. Distribution Grid */}
      <div className="protocols-grid">
        {/* Card 1: Transport Protocols (Mutually exclusive 100%) */}
        <div className="protocol-card">
          <div className="protocol-card-title">
            <span>Transport Protocol Distribution</span>
            <PieChart size={15} style={{ color: 'var(--accent-cyan)' }} />
          </div>

          <div className="distribution-bar-track">
            <div className="dist-segment dist-segment--tcp" style={{ width: `${tcpPct}%` }} title={`TCP: ${tcpPct.toFixed(1)}%`} />
            <div className="dist-segment dist-segment--udp" style={{ width: `${udpPct}%` }} title={`UDP: ${udpPct.toFixed(1)}%`} />
            <div className="dist-segment dist-segment--icmp" style={{ width: `${icmpPct}%` }} title={`ICMP: ${icmpPct.toFixed(1)}%`} />
            <div className="dist-segment dist-segment--other" style={{ width: `${otherPct}%` }} title={`Other: ${otherPct.toFixed(1)}%`} />
          </div>

          <div className="protocol-legend-list">
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: 'var(--accent-cyan)' }} />
                <span>TCP</span>
              </div>
              <span className="mono">{currentMetric?.tcp_packets ?? 0} ({tcpPct.toFixed(1)}%)</span>
            </div>
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: 'var(--status-warning)' }} />
                <span>UDP</span>
              </div>
              <span className="mono">{currentMetric?.udp_packets ?? 0} ({udpPct.toFixed(1)}%)</span>
            </div>
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: '#a855f7' }} />
                <span>ICMP</span>
              </div>
              <span className="mono">{currentMetric?.icmp_packets ?? 0} ({icmpPct.toFixed(1)}%)</span>
            </div>
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: '#64748b' }} />
                <span>Other Transport</span>
              </div>
              <span className="mono">{currentMetric?.other_transport_packets ?? 0} ({otherPct.toFixed(1)}%)</span>
            </div>
          </div>

          {/* DNS Subset Note */}
          <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
            <span>DNS Queries (Port 53 subset):</span>
            <span className="mono" style={{ color: '#38bdf8' }}>{currentMetric?.dns_packets ?? 0} packets</span>
          </div>
        </div>

        {/* Card 2: Network Layer Breakdown (IPv4 vs IPv6) */}
        <div className="protocol-card">
          <div className="protocol-card-title">
            <span>Network Layer (IP Family)</span>
            <Layers size={15} style={{ color: '#3b82f6' }} />
          </div>

          <div className="distribution-bar-track">
            <div className="dist-segment dist-segment--ipv4" style={{ width: `${ipv4Pct}%` }} title={`IPv4: ${ipv4Pct.toFixed(1)}%`} />
            <div className="dist-segment dist-segment--ipv6" style={{ width: `${ipv6Pct}%` }} title={`IPv6: ${ipv6Pct.toFixed(1)}%`} />
          </div>

          <div className="protocol-legend-list">
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: '#3b82f6' }} />
                <span>IPv4</span>
              </div>
              <span className="mono">{ipv4Count} ({ipv4Pct.toFixed(1)}%)</span>
            </div>
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: '#10b981' }} />
                <span>IPv6</span>
              </div>
              <span className="mono">{ipv6Count} ({ipv6Pct.toFixed(1)}%)</span>
            </div>
            <div className="protocol-legend-item">
              <div className="protocol-legend-left">
                <span className="legend-color-dot" style={{ background: '#64748b' }} />
                <span>Non-IP / Other</span>
              </div>
              <span className="mono">{otherNetCount}</span>
            </div>
          </div>

          <div style={{ marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span>Window interval: {currentMetric?.window_duration_seconds ?? 2.0}s</span>
          </div>
        </div>
      </div>

      {/* 5. Historical Table */}
      <div className="connections-table-container" style={{ maxHeight: '200px' }}>
        <table className="connections-table">
          <thead>
            <tr>
              <th>TIME (UTC)</th>
              <th>STATUS</th>
              <th>TOTAL PACKETS</th>
              <th>PPS</th>
              <th>TCP</th>
              <th>UDP</th>
              <th>ICMP</th>
              <th>DNS</th>
              <th>IPV4</th>
              <th>IPV6</th>
              <th>NON-IP</th>
            </tr>
          </thead>
          <tbody>
            {history.map(w => (
              <tr key={w.window_id}>
                <td className="mono" style={{ fontSize: '11px' }}>{w.timestamp_utc}</td>
                <td>
                  <span className={`state-badge ${w.status === 'LIVE' ? 'state-badge--established' : 'state-badge--timewait'}`}>
                    {w.status}
                  </span>
                </td>
                <td className="mono">{w.total_packets}</td>
                <td className="mono">{w.packets_per_second}</td>
                <td className="mono" style={{ color: 'var(--accent-cyan)' }}>{w.tcp_packets}</td>
                <td className="mono" style={{ color: 'var(--status-warning)' }}>{w.udp_packets}</td>
                <td className="mono" style={{ color: '#a855f7' }}>{w.icmp_packets}</td>
                <td className="mono" style={{ color: '#38bdf8' }}>{w.dns_packets}</td>
                <td className="mono text-muted">{w.ipv4_packets}</td>
                <td className="mono text-muted">{w.ipv6_packets}</td>
                <td className="mono text-dim">{w.non_ip_packets ?? 0}</td>
              </tr>
            ))}
            {history.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                  No historical protocol windows recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Notice */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', padding: '0 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ShieldCheck size={12} style={{ color: 'var(--status-live)' }} />
          <span>Packet metadata and transport counters only. No payload inspection or payload storage performed.</span>
        </div>
      </div>
    </div>
  );
};
