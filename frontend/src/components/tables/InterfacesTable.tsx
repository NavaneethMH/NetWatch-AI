import React from 'react';
import type { InterfaceInfo, InterfaceThroughput } from '../../types/telemetry';
import { CheckCircle2, XCircle } from 'lucide-react';

interface InterfacesTableProps {
  interfaces: InterfaceInfo[];
  throughputList?: InterfaceThroughput[];
}

export const InterfacesTable: React.FC<InterfacesTableProps> = ({
  interfaces,
  throughputList = []
}) => {
  const throughputMap = new Map<string, InterfaceThroughput>();
  throughputList.forEach(item => {
    throughputMap.set(item.name, item);
  });

  return (
    <div className="noc-panel">
      <div className="noc-panel-header">
        <div className="noc-panel-title-group">
          <h3 className="noc-panel-title">HOST NETWORK ADAPTERS</h3>
          <span className="noc-panel-subtitle">Hardware interfaces and active IPv4/MAC bindings</span>
        </div>
        <span className="mono text-dim" style={{ fontSize: '11px' }}>
          {interfaces.length} detected
        </span>
      </div>

      {interfaces.length === 0 ? (
        <div className="noc-empty-state">
          <span className="noc-empty-title">No network interfaces detected</span>
          <span className="noc-empty-desc">Check system network stack permissions.</span>
        </div>
      ) : (
        <div className="noc-table-wrap">
          <table className="noc-table">
            <thead>
              <tr>
                <th style={{ width: '85px' }}>STATUS</th>
                <th>INTERFACE</th>
                <th>IPV4 ADDRESS</th>
                <th>MAC ADDRESS</th>
                <th>SPEED</th>
                <th>MTU</th>
                <th>↓ THROUGHPUT</th>
                <th>↑ THROUGHPUT</th>
              </tr>
            </thead>
            <tbody>
              {interfaces.map(iface => {
                const tp = throughputMap.get(iface.name);
                const ipv4 = iface.addresses.find(a => a.family === 'IPv4')?.address || '—';
                const mac = iface.addresses.find(a => a.family === 'MAC')?.address || '—';
                const isUp = iface.is_up;

                return (
                  <tr key={iface.name} className={!isUp ? 'row-down' : ''}>
                    <td>
                      {isUp ? (
                        <span className="noc-tag-live">
                          <CheckCircle2 size={11} /> UP
                        </span>
                      ) : (
                        <span className="noc-tag-down">
                          <XCircle size={11} /> DOWN
                        </span>
                      )}
                    </td>
                    <td className="font-semibold text-main">
                      {iface.name}
                    </td>
                    <td className="mono color-cyan">
                      {ipv4}
                    </td>
                    <td className="mono text-muted" style={{ fontSize: '11px' }}>
                      {mac}
                    </td>
                    <td className="mono text-muted">
                      {iface.speed_mbps && iface.speed_mbps > 0 ? `${iface.speed_mbps} Mbps` : '—'}
                    </td>
                    <td className="mono text-dim">
                      {iface.mtu ?? '—'}
                    </td>
                    <td className="mono color-dl">
                      {tp?.download_mbps !== null && tp?.download_mbps !== undefined 
                        ? `${tp.download_mbps.toFixed(3)} Mbps` 
                        : '—'}
                    </td>
                    <td className="mono color-ul">
                      {tp?.upload_mbps !== null && tp?.upload_mbps !== undefined 
                        ? `${tp.upload_mbps.toFixed(3)} Mbps` 
                        : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
