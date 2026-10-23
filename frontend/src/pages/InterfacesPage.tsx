import React from 'react';
import type { NetworkThroughput, SystemTelemetry } from '../types/telemetry';
import { formatBytes } from '../utils/formatters';
import { InterfacesTable } from '../components/tables/InterfacesTable';

interface InterfacesPageProps {
  system: SystemTelemetry | null;
  network: NetworkThroughput | null;
}

export const InterfacesPage: React.FC<InterfacesPageProps> = ({ system, network }) => {
  return (
    <div className="noc-page-container">
      <InterfacesTable 
        interfaces={system?.interfaces || []} 
        throughputList={network?.interfaces || []} 
      />

      <div className="noc-grid-cards" style={{ marginTop: '20px' }}>
        {network?.interfaces?.map(iface => {
          const sysIface = system?.interfaces?.find(si => si.name === iface.name);
          const ipv4 = sysIface?.addresses.find(a => a.family === 'IPv4')?.address || '—';
          const mac = sysIface?.addresses.find(a => a.family === 'MAC')?.address || '—';

          return (
            <div key={iface.name} className="noc-panel">
              <div className="noc-panel-header">
                <div className="noc-panel-title-group">
                  <h4 className="noc-panel-title">{iface.name}</h4>
                  <span className="noc-panel-subtitle">
                    {ipv4 !== '—' ? `${ipv4} · ` : ''}{mac !== '—' ? mac : iface.is_up ? 'ONLINE / CONNECTED' : 'DISCONNECTED'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {sysIface?.speed_mbps && sysIface.speed_mbps > 0 && (
                    <span className="mono text-muted" style={{ fontSize: '11px' }}>
                      {sysIface.speed_mbps} Mbps
                    </span>
                  )}
                  <span className={iface.is_up ? 'noc-tag-live' : 'noc-tag-down'}>
                    {iface.is_up ? 'UP' : 'DOWN'}
                  </span>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '12px' }}>
                <div className="noc-metric-tile">
                  <span className="noc-tile-label">CURRENT DOWNLOAD</span>
                  <span className="mono color-dl" style={{ fontSize: '18px', fontWeight: 600 }}>
                    {iface.download_mbps !== null && iface.download_mbps !== undefined ? `${iface.download_mbps.toFixed(3)} Mbps` : '—'}
                  </span>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '4px' }}>
                    <span className="mono text-dim">Recv: {formatBytes(iface.bytes_recv)}</span>
                    <span className="mono text-dim">{iface.packets_recv?.toLocaleString() ?? 0} pkts</span>
                  </div>
                </div>

                <div className="noc-metric-tile">
                  <span className="noc-tile-label">CURRENT UPLOAD</span>
                  <span className="mono color-ul" style={{ fontSize: '18px', fontWeight: 600 }}>
                    {iface.upload_mbps !== null && iface.upload_mbps !== undefined ? `${iface.upload_mbps.toFixed(3)} Mbps` : '—'}
                  </span>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '4px' }}>
                    <span className="mono text-dim">Sent: {formatBytes(iface.bytes_sent)}</span>
                    <span className="mono text-dim">{iface.packets_sent?.toLocaleString() ?? 0} pkts</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
