import React from 'react';
import { Activity, ShieldCheck, AlertTriangle, AlertOctagon, HelpCircle } from 'lucide-react';
import type { HealthScoreData } from '../../types/telemetry';

interface NetworkHealthModuleProps {
  health: HealthScoreData | null;
  isOffline?: boolean;
}

export const NetworkHealthModule: React.FC<NetworkHealthModuleProps> = ({
  health,
  isOffline = false
}) => {
  if (isOffline) {
    return (
      <div className="noc-card noc-health-module">
        <div className="noc-health-header">
          <div className="noc-card-title">
            <Activity size={14} className="text-secondary" />
            <span>NETWORK HEALTH</span>
          </div>
          <span className="noc-badge noc-badge-stale">OFFLINE</span>
        </div>
        <div className="noc-health-body">
          <div className="noc-health-score-row">
            <span className="noc-health-num mono">—</span>
            <span className="noc-health-denom mono">/ 100</span>
          </div>
          <p className="noc-health-subtext">Telemetry connection offline. Live score unavailable.</p>
        </div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="noc-card noc-health-module">
        <div className="noc-health-header">
          <div className="noc-card-title">
            <Activity size={14} className="text-accent" />
            <span>NETWORK HEALTH</span>
          </div>
          <span className="noc-badge noc-badge-warming">WARMING UP</span>
        </div>
        <div className="noc-health-body">
          <div className="noc-health-score-row">
            <span className="noc-health-num mono">...</span>
            <span className="noc-health-denom mono">/ 100</span>
          </div>
          <p className="noc-health-subtext">Computing initial deterministic health metrics...</p>
        </div>
      </div>
    );
  }

  const { score, status, deductions = [] } = health;

  const getStatusBadge = () => {
    switch (status) {
      case 'HEALTHY':
        return (
          <span className="noc-badge noc-badge-healthy">
            <ShieldCheck size={12} />
            <span>HEALTHY</span>
          </span>
        );
      case 'DEGRADED':
        return (
          <span className="noc-badge noc-badge-warning">
            <AlertTriangle size={12} />
            <span>DEGRADED</span>
          </span>
        );
      case 'POOR':
        return (
          <span className="noc-badge noc-badge-poor">
            <AlertTriangle size={12} />
            <span>POOR</span>
          </span>
        );
      case 'CRITICAL':
        return (
          <span className="noc-badge noc-badge-critical">
            <AlertOctagon size={12} />
            <span>CRITICAL</span>
          </span>
        );
      default:
        return (
          <span className="noc-badge">
            <HelpCircle size={12} />
            <span>{status}</span>
          </span>
        );
    }
  };

  const getScoreColorClass = () => {
    if (score >= 90) return 'text-healthy';
    if (score >= 70) return 'text-warning';
    if (score >= 40) return 'text-poor';
    return 'text-critical';
  };

  return (
    <div className="noc-card noc-health-module">
      <div className="noc-health-header">
        <div className="noc-card-title">
          <Activity size={14} className="text-accent" />
          <span>NETWORK HEALTH</span>
        </div>
        {getStatusBadge()}
      </div>

      <div className="noc-health-body">
        <div className="noc-health-primary">
          <div className="noc-health-score-row">
            <span className={`noc-health-num mono ${getScoreColorClass()}`}>{score}</span>
            <span className="noc-health-denom mono">/ 100</span>
          </div>

          <div className="noc-health-bar-container">
            <div
              className={`noc-health-bar-fill ${status.toLowerCase()}`}
              style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
            />
          </div>
        </div>

        <div className="noc-health-deductions">
          {deductions.length === 0 ? (
            <div className="noc-health-optimal">
              <span className="noc-dot dot-live" />
              <span>All monitored network & host metrics within optimal thresholds.</span>
            </div>
          ) : (
            <div className="noc-deductions-list">
              <span className="noc-deductions-label">Deductions ({deductions.length}):</span>
              <div className="noc-deductions-chips">
                {deductions.map((d, idx) => (
                  <div key={idx} className="noc-deduction-chip" title={`${d.category}: ${d.reason} (${d.observed_value || ''})`}>
                    <span className="noc-deduction-points mono">-{d.points}</span>
                    <span className="noc-deduction-text">{d.reason}</span>
                    {d.observed_value && (
                      <span className="noc-deduction-val mono">{d.observed_value}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
