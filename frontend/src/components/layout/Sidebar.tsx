import React from 'react';
import { 
  LayoutDashboard, 
  Network, 
  Layers, 
  History, 
  Wifi,
  Bell, 
  GitCommit, 
  Activity,
  BrainCircuit 
} from 'lucide-react';
import type { ActivePage } from '../../types/telemetry';

interface SidebarProps {
  activePage: ActivePage;
  onSelectPage: (page: ActivePage) => void;
  interfaceCount?: number;
  activeAlertCount?: number;
  onlineDeviceCount?: number;
  connectionCount?: number;
  protocolStatus?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onSelectPage,
  interfaceCount = 0,
  activeAlertCount = 0,
  onlineDeviceCount = 0,
  connectionCount = 0,
  protocolStatus = 'PERMISSION_REQUIRED',
}) => {
  return (
    <aside className="noc-sidebar">
      <div className="noc-nav-group">
        <span className="noc-nav-label">OPERATIONS</span>
        
        <button
          onClick={() => onSelectPage('overview')}
          className={`noc-nav-item ${activePage === 'overview' ? 'active' : ''}`}
        >
          <LayoutDashboard size={15} />
          <span>Overview</span>
        </button>

        <button
          onClick={() => onSelectPage('network')}
          className={`noc-nav-item ${activePage === 'network' ? 'active' : ''}`}
        >
          <Network size={15} />
          <span>Network</span>
        </button>

        <button
          onClick={() => onSelectPage('interfaces')}
          className={`noc-nav-item ${activePage === 'interfaces' ? 'active' : ''}`}
        >
          <Layers size={15} />
          <span>Interfaces</span>
          {interfaceCount > 0 && (
            <span className="noc-nav-counter mono">{interfaceCount}</span>
          )}
        </button>

        <button
          onClick={() => onSelectPage('connections')}
          className={`noc-nav-item ${activePage === 'connections' ? 'active' : ''}`}
          id="nav-connections"
        >
          <GitCommit size={15} />
          <span>Connections</span>
          {connectionCount > 0 && (
            <span className="noc-nav-counter mono">{connectionCount}</span>
          )}
        </button>

        <button
          onClick={() => onSelectPage('protocols')}
          className={`noc-nav-item ${activePage === 'protocols' ? 'active' : ''}`}
          id="nav-protocols"
        >
          <Activity size={15} />
          <span>Protocols</span>
          <span className={`noc-nav-counter mono ${protocolStatus === 'LIVE' ? 'text-live' : ''}`} style={{ fontSize: '9px' }}>
            {protocolStatus === 'LIVE' ? 'LIVE' : 'PERM'}
          </span>
        </button>

        <button
          onClick={() => onSelectPage('history')}
          className={`noc-nav-item ${activePage === 'history' ? 'active' : ''}`}
        >
          <History size={15} />
          <span>History</span>
        </button>

        <button
          onClick={() => onSelectPage('alerts')}
          className={`noc-nav-item ${activePage === 'alerts' ? 'active' : ''}`}
          id="nav-alerts"
        >
          <Bell size={15} />
          <span>Alerts</span>
          {activeAlertCount > 0 && (
            <span className="noc-nav-counter mono text-warning">{activeAlertCount}</span>
          )}
        </button>

        <button
          onClick={() => onSelectPage('devices')}
          className={`noc-nav-item ${activePage === 'devices' ? 'active' : ''}`}
          id="nav-devices"
        >
          <Wifi size={15} />
          <span>Devices</span>
          {onlineDeviceCount > 0 && (
            <span className="noc-nav-counter mono">{onlineDeviceCount}</span>
          )}
        </button>
      </div>

      <div className="noc-nav-group">
        <span className="noc-nav-label">OPERATIONAL READINESS</span>

        <div className="noc-nav-item" title="Phase 13 Hardened & Release Ready" style={{ cursor: 'default', opacity: 0.85 }}>
          <BrainCircuit size={15} style={{ color: 'var(--accent-cyan)' }} />
          <span>Security & Auth</span>
          <span className="noc-badge-phase" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>P13 READY</span>
        </div>
      </div>

      <div className="noc-sidebar-footer">
        <div className="noc-host-chip">
          <span className="noc-host-label">HOST SYSTEM</span>
          <span className="noc-host-val mono">Windows x64 Localhost</span>
        </div>
      </div>
    </aside>
  );
};
