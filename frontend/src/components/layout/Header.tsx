import React, { useState } from 'react';
import { 
  Activity, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  Database, 
  Radio,
  Key
} from 'lucide-react';
import type { ConnectionState } from '../../types/telemetry';
import { AuthModal } from '../modals/AuthModal';
import { getOperatorKey } from '../../utils/auth';

interface HeaderProps {
  connState: ConnectionState;
  activeInterface: string;
  lastSyncFormatted: string;
  onReconnect: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  connState,
  activeInterface,
  lastSyncFormatted,
  onReconnect
}) => {
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const hasKey = Boolean(getOperatorKey());
  return (
    <header className="noc-header">
      <div className="noc-header-brand">
        <div className="noc-logo-badge">
          <Activity size={16} strokeWidth={2.6} />
        </div>
        <div className="noc-brand-text">
          <span className="noc-brand-title">
            NETWATCH <span className="noc-brand-accent">AI</span>
          </span>
          <span className="noc-brand-subtitle">NOC OBSERVABILITY</span>
        </div>
      </div>

      <div className="noc-header-controls">
        <div className="noc-badge noc-badge-adapter" title="Primary active interface">
          <Radio size={12} color="var(--accent-cyan)" />
          <span className="mono">{activeInterface}</span>
        </div>

        <div className="noc-badge noc-badge-db" title="Autonomous SQLite WAL Persistence Engine">
          <Database size={12} color="#10b981" />
          <span>SQLITE WAL</span>
        </div>

        {connState === 'LIVE' && (
          <div className="noc-badge badge-live" title="Real-time WebSocket stream active">
            <span className="pulse-dot"></span>
            <Wifi size={12} />
            <span>LIVE</span>
          </div>
        )}

        {connState === 'DELAYED' && (
          <div className="noc-badge badge-warning" title="No telemetry arrived for >4.5s">
            <span className="pulse-dot" style={{ backgroundColor: 'var(--status-warning)' }}></span>
            <span>DELAYED</span>
          </div>
        )}

        {connState === 'CONNECTING' && (
          <div className="noc-badge badge-info" title="Establishing WebSocket handshake">
            <RefreshCw size={11} className="animate-spin" />
            <span>CONNECTING</span>
          </div>
        )}

        {connState === 'OFFLINE' && (
          <div className="noc-badge badge-critical" title="Disconnected from /ws/telemetry">
            <span className="pulse-dot" style={{ backgroundColor: 'var(--status-critical)' }}></span>
            <WifiOff size={12} />
            <span>OFFLINE</span>
          </div>
        )}

        <div className="noc-sync-info">
          <span className="noc-sync-label">Updated</span>
          <span className="mono noc-sync-val">{lastSyncFormatted}</span>
        </div>

        <button
          onClick={() => setIsAuthOpen(true)}
          className={`noc-btn-icon ${hasKey ? 'active-key' : ''}`}
          title={hasKey ? 'Operator Key configured in session' : 'Configure Operator API Key'}
          style={hasKey ? { color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.4)' } : undefined}
          id="header-auth-btn"
        >
          <Key size={13} />
        </button>

        <button
          onClick={onReconnect}
          className="noc-btn-icon"
          title="Reconnect WebSocket stream"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
      />
    </header>
  );
};
