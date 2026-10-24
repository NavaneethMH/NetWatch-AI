import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bell, 
  AlertTriangle, 
  AlertOctagon, 
  Info, 
  CheckCircle2, 
  Eye, 
  Check, 
  RefreshCw,
  X,
  Filter
} from 'lucide-react';
import type { AlertItemData, AlertSummaryData } from '../types/telemetry';
import { getAuthHeaders } from '../utils/auth';
import { apiUrl } from '../utils/api';

interface AlertsPageProps {
  alertsSummary: AlertSummaryData | null;
}

export const AlertsPage: React.FC<AlertsPageProps> = ({ alertsSummary }) => {
  const [alerts, setAlerts] = useState<AlertItemData[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [selectedAlert, setSelectedAlert] = useState<AlertItemData | null>(null);
  const [acknowledgingId, setAcknowledgingId] = useState<number | null>(null);

  const fetchAlerts = useCallback(async () => {
    setIsLoading(true);
    try {
      let url = apiUrl('/api/alerts?limit=150');
      if (statusFilter !== 'ALL') url += `&status=${statusFilter}`;
      if (severityFilter !== 'ALL') url += `&severity=${severityFilter}`;
      
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setAlerts(data.items || []);
      }
    } catch (e) {
      console.error('Failed to fetch alerts:', e);
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, severityFilter]);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const handleAcknowledge = async (alertId: number) => {
    setAcknowledgingId(alertId);
    try {
      const res = await fetch(apiUrl(`/api/alerts/${alertId}/acknowledge`), {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setAlerts(prev => prev.map(a => a.id === alertId ? data.alert : a));
        if (selectedAlert && selectedAlert.id === alertId) {
          setSelectedAlert(data.alert);
        }
      }
    } catch (e) {
      console.error('Failed to acknowledge alert:', e);
    } finally {
      setAcknowledgingId(null);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="noc-badge noc-badge-critical">
            <AlertOctagon size={12} />
            <span>CRITICAL</span>
          </span>
        );
      case 'WARNING':
        return (
          <span className="noc-badge noc-badge-warning">
            <AlertTriangle size={12} />
            <span>WARNING</span>
          </span>
        );
      default:
        return (
          <span className="noc-badge noc-badge-info">
            <Info size={12} />
            <span>INFO</span>
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'OPEN':
        return <span className="noc-badge noc-badge-open">OPEN</span>;
      case 'ACKNOWLEDGED':
        return <span className="noc-badge noc-badge-ack">ACKNOWLEDGED</span>;
      case 'RESOLVED':
        return <span className="noc-badge noc-badge-resolved">RESOLVED</span>;
      default:
        return <span className="noc-badge">{status}</span>;
    }
  };

  return (
    <div className="noc-page-container">
      {/* 1. Header & Summary Chips */}
      <div className="noc-section-header">
        <div>
          <h2 className="noc-section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bell size={16} className="text-accent" />
            <span>ALERT MANAGEMENT</span>
          </h2>
          <p className="noc-section-subtitle">
            Deterministic rule-based anomaly notifications with consecutive-sample dampening.
          </p>
        </div>
        <button
          onClick={fetchAlerts}
          className="noc-btn-secondary"
          title="Refresh Alerts"
          disabled={isLoading}
        >
          <RefreshCw size={13} className={isLoading ? 'noc-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="noc-summary-grid">
        <div className="noc-card noc-summary-card">
          <span className="noc-summary-label">ACTIVE ALERTS</span>
          <span className="noc-summary-value mono">{alertsSummary?.total_active ?? 0}</span>
          <span className="noc-summary-sub mono">Open: {alertsSummary?.open_count ?? 0}</span>
        </div>
        <div className="noc-card noc-summary-card">
          <span className="noc-summary-label">CRITICAL</span>
          <span className={`noc-summary-value mono ${alertsSummary?.critical_count ? 'text-critical' : ''}`}>
            {alertsSummary?.critical_count ?? 0}
          </span>
          <span className="noc-summary-sub">Immediate attention required</span>
        </div>
        <div className="noc-card noc-summary-card">
          <span className="noc-summary-label">WARNING</span>
          <span className={`noc-summary-value mono ${alertsSummary?.warning_count ? 'text-warning' : ''}`}>
            {alertsSummary?.warning_count ?? 0}
          </span>
          <span className="noc-summary-sub">Threshold violations</span>
        </div>
        <div className="noc-card noc-summary-card">
          <span className="noc-summary-label">ACKNOWLEDGED</span>
          <span className="noc-summary-value mono text-secondary">
            {alertsSummary?.acknowledged_count ?? 0}
          </span>
          <span className="noc-summary-sub">Under investigation</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="noc-card noc-filter-toolbar">
        <div className="noc-filter-group">
          <span className="noc-filter-label"><Filter size={12} /> Status:</span>
          {['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map(st => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`noc-tab-btn ${statusFilter === st ? 'active' : ''}`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="noc-filter-group">
          <span className="noc-filter-label">Severity:</span>
          {['ALL', 'CRITICAL', 'WARNING', 'INFO'].map(sev => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`noc-tab-btn ${severityFilter === sev ? 'active' : ''}`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Alerts Table or Empty State */}
      <div className="noc-card noc-table-card">
        {isLoading && alerts.length === 0 ? (
          <div className="noc-empty-state">
            <RefreshCw size={24} className="noc-spin text-secondary" />
            <p className="noc-empty-title">Loading telemetry alerts...</p>
          </div>
        ) : alerts.length === 0 ? (
          <div className="noc-empty-state">
            <CheckCircle2 size={32} className="text-healthy" />
            <p className="noc-empty-title">No active alerts.</p>
            <p className="noc-empty-desc">
              All monitored conditions are within configured thresholds.
            </p>
          </div>
        ) : (
          <div className="noc-table-scroll">
            <table className="noc-data-table">
              <thead>
                <tr>
                  <th style={{ width: '110px' }}>SEVERITY</th>
                  <th>ALERT / MESSAGE</th>
                  <th style={{ width: '110px' }}>SOURCE</th>
                  <th style={{ width: '130px' }}>METRIC / OBSERVED</th>
                  <th style={{ width: '160px' }}>OPENED</th>
                  <th style={{ width: '160px' }}>LAST SEEN</th>
                  <th style={{ width: '110px' }}>STATUS</th>
                  <th style={{ width: '130px', textAlign: 'right' }}>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map(a => (
                  <tr key={a.id} className={`noc-alert-row ${a.status.toLowerCase()}`}>
                    <td>{getSeverityBadge(a.severity)}</td>
                    <td>
                      <div className="noc-alert-title mono">{a.type}</div>
                      <div className="noc-alert-msg">{a.message}</div>
                    </td>
                    <td>
                      <span className="noc-source-chip mono">{a.source}</span>
                    </td>
                    <td>
                      <div className="noc-metric-val mono">
                        {a.observed_value !== null ? `${a.observed_value.toFixed(1)}` : '—'}
                        {a.threshold_value !== null && (
                          <span className="noc-thresh-val"> / {a.threshold_value.toFixed(1)}</span>
                        )}
                      </div>
                      <div className="noc-metric-name mono">{a.metric_name}</div>
                    </td>
                    <td>
                      <span className="mono text-secondary" title={a.opened_at_utc}>
                        {new Date(a.opened_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                    </td>
                    <td>
                      <span className="mono text-secondary" title={a.last_seen_at_utc}>
                        {new Date(a.last_seen_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                      {a.occurrence_count > 1 && (
                        <span className="noc-count-badge mono">×{a.occurrence_count}</span>
                      )}
                    </td>
                    <td>{getStatusBadge(a.status)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="noc-actions-cell">
                        {a.status === 'OPEN' && (
                          <button
                            onClick={() => handleAcknowledge(a.id)}
                            disabled={acknowledgingId === a.id}
                            className="noc-btn-ack"
                            title="Acknowledge alert"
                          >
                            <Check size={12} />
                            <span>Ack</span>
                          </button>
                        )}
                        <button
                          onClick={() => setSelectedAlert(a)}
                          className="noc-btn-inspect"
                          title="Inspect alert details"
                        >
                          <Eye size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 3. Detail Drawer / Modal */}
      {selectedAlert && (
        <div className="noc-modal-backdrop" onClick={() => setSelectedAlert(null)}>
          <div className="noc-modal-content" onClick={e => e.stopPropagation()}>
            <div className="noc-modal-header">
              <div className="noc-modal-title-group">
                {getSeverityBadge(selectedAlert.severity)}
                <h3 className="noc-modal-title mono">{selectedAlert.type}</h3>
              </div>
              <button 
                className="noc-modal-close" 
                onClick={() => setSelectedAlert(null)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="noc-modal-body">
              <p className="noc-modal-message">{selectedAlert.message}</p>

              <div className="noc-detail-grid">
                <div className="noc-detail-item">
                  <span className="noc-detail-label">ALERT ID</span>
                  <span className="noc-detail-value mono">{selectedAlert.alert_id}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">STATUS</span>
                  <span className="noc-detail-value">{getStatusBadge(selectedAlert.status)}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">SOURCE</span>
                  <span className="noc-detail-value mono">{selectedAlert.source}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">METRIC</span>
                  <span className="noc-detail-value mono">{selectedAlert.metric_name}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">OBSERVED VALUE</span>
                  <span className="noc-detail-value mono">
                    {selectedAlert.observed_value !== null ? selectedAlert.observed_value.toFixed(2) : 'Unavailable'}
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">THRESHOLD</span>
                  <span className="noc-detail-value mono">
                    {selectedAlert.threshold_value !== null ? selectedAlert.threshold_value.toFixed(2) : 'N/A'}
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">OCCURRENCE COUNT</span>
                  <span className="noc-detail-value mono">{selectedAlert.occurrence_count}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">OPENED AT (UTC)</span>
                  <span className="noc-detail-value mono">{selectedAlert.opened_at_utc}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">LAST SEEN (UTC)</span>
                  <span className="noc-detail-value mono">{selectedAlert.last_seen_at_utc}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">ACKNOWLEDGED AT</span>
                  <span className="noc-detail-value mono">
                    {selectedAlert.acknowledged_at_utc || 'Not acknowledged'}
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">RESOLVED AT</span>
                  <span className="noc-detail-value mono">
                    {selectedAlert.resolved_at_utc || 'Condition still active'}
                  </span>
                </div>
              </div>
            </div>

            <div className="noc-modal-footer">
              {selectedAlert.status === 'OPEN' && (
                <button
                  onClick={() => handleAcknowledge(selectedAlert.id)}
                  className="noc-btn-ack"
                  disabled={acknowledgingId === selectedAlert.id}
                >
                  <Check size={14} />
                  <span>Acknowledge Alert</span>
                </button>
              )}
              <button 
                className="noc-btn-secondary" 
                onClick={() => setSelectedAlert(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
