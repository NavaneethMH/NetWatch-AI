import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { apiUrl } from '../utils/api';
import { 
  GitCommit, 
  Search, 
  RefreshCw, 
  Filter, 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown,
  ShieldCheck,
  X
} from 'lucide-react';
import type { ConnectionItem, ConnectionListResponse, ConnectionSummary } from '../types/telemetry';
import '../devices.css';
import '../connections.css';

interface ConnectionsPageProps {
  connectionSummary?: ConnectionSummary | null;
}

type SortField = 'process_name' | 'pid' | 'protocol' | 'local_port' | 'remote_port' | 'state' | 'last_observed';
type SortOrder = 'asc' | 'desc';

export const ConnectionsPage: React.FC<ConnectionsPageProps> = ({ connectionSummary }) => {
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConn, setSelectedConn] = useState<ConnectionItem | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [protoFilter, setProtoFilter] = useState<'ALL' | 'TCP' | 'UDP'>('ALL');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [procFilter, setProcFilter] = useState<string>('');

  // Sorting
  const [sortField, setSortField] = useState<SortField>('state');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // Fetch connections from GET /api/connections (reads existing state, no extra OS scan)
  const fetchConnections = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (protoFilter !== 'ALL') params.append('protocol', protoFilter);
      if (stateFilter !== 'ALL') params.append('state', stateFilter);
      if (procFilter.trim()) params.append('process', procFilter.trim());
      if (search.trim()) params.append('search', search.trim());
      params.append('limit', '500');

      const res = await fetch(apiUrl(`/api/connections?${params.toString()}`));
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: ConnectionListResponse = await res.json();
      setConnections(data.items);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch active connections');
    } finally {
      setLoading(false);
    }
  }, [protoFilter, stateFilter, procFilter, search]);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  // Periodic refresh every 5s so table reflects collector updates
  useEffect(() => {
    const timer = setInterval(() => {
      fetchConnections();
    }, 5000);
    return () => clearInterval(timer);
  }, [fetchConnections]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const sortedConnections = useMemo(() => {
    const items = [...connections];
    items.sort((a, b) => {
      let vA: any = a[sortField];
      let vB: any = b[sortField];

      if (sortField === 'local_port') {
        vA = a.local_port ?? -1;
        vB = b.local_port ?? -1;
      } else if (sortField === 'remote_port') {
        vA = a.remote_port ?? -1;
        vB = b.remote_port ?? -1;
      } else if (sortField === 'pid') {
        vA = a.pid ?? -1;
        vB = b.pid ?? -1;
      } else if (sortField === 'process_name') {
        vA = (a.process_name || 'zzz').toLowerCase();
        vB = (b.process_name || 'zzz').toLowerCase();
      } else if (typeof vA === 'string') {
        vA = vA.toLowerCase();
        vB = (vB || '').toLowerCase();
      }

      if (vA < vB) return sortOrder === 'asc' ? -1 : 1;
      if (vA > vB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
    return items;
  }, [connections, sortField, sortOrder]);

  // Unique states present in connections for state filter dropdown
  const availableStates = useMemo(() => {
    const s = new Set<string>();
    connections.forEach(c => {
      if (c.state) s.add(c.state.toUpperCase());
    });
    return Array.from(s).sort();
  }, [connections]);

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return <ArrowUpDown size={12} style={{ opacity: 0.3 }} />;
    return sortOrder === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
  };

  const getStateBadgeClass = (st: string) => {
    const u = (st || '').toUpperCase();
    if (u === 'ESTABLISHED') return 'state-badge--established';
    if (u === 'LISTEN') return 'state-badge--listen';
    if (u === 'TIME_WAIT') return 'state-badge--timewait';
    if (u === 'CLOSE_WAIT') return 'state-badge--closewait';
    return 'state-badge--other';
  };

  return (
    <div className="page-container">
      {/* 1. Header */}
      <div className="page-header">
        <div className="page-header__left">
          <GitCommit size={22} className="page-icon" />
          <div>
            <h1 className="page-title">Active Host Connections</h1>
            <p className="page-subtitle">
              Real-time socket inspection & process mapping on this host (Phase 10)
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={() => fetchConnections()}
            className="devices-btn devices-btn--secondary"
            title="Refresh connections table"
            disabled={loading}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. KPI Summary Bar (populated from WebSocket / backend) */}
      <div className="conn-kpi-bar">
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Total Sockets</span>
          <span className="conn-kpi-val mono">{connectionSummary?.total ?? connections.length}</span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Established</span>
          <span className="conn-kpi-val mono" style={{ color: 'var(--status-live)' }}>
            {connectionSummary?.established ?? 0}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Listening</span>
          <span className="conn-kpi-val mono" style={{ color: '#60a5fa' }}>
            {connectionSummary?.listening ?? 0}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">TCP / UDP</span>
          <span className="conn-kpi-val mono" style={{ fontSize: '15px' }}>
            {connectionSummary ? `${connectionSummary.tcp} / ${connectionSummary.udp}` : '—'}
          </span>
        </div>
        <div className="conn-kpi-card">
          <span className="conn-kpi-label">Scan Latency</span>
          <span className="conn-kpi-val mono" style={{ fontSize: '15px', color: 'var(--accent-cyan)' }}>
            {connectionSummary?.scan_duration_ms != null ? `${connectionSummary.scan_duration_ms} ms` : '—'}
          </span>
        </div>
      </div>

      {/* 3. Search & Filter Bar */}
      <div className="devices-status-bar" style={{ flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flex: 1, minWidth: '220px' }}>
          <div style={{ position: 'relative', width: '100%', maxWidth: '300px', display: 'flex', alignItems: 'center' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-dim)', pointerEvents: 'none' }} />
            <input
              type="text"
              placeholder="Search IP, port, process, PID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="devices-search-input"
              style={{ width: '100%', paddingLeft: '32px' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '4px' }}>
            {(['ALL', 'TCP', 'UDP'] as const).map(p => (
              <button
                key={p}
                onClick={() => setProtoFilter(p)}
                className={`devices-filter-btn ${protoFilter === p ? 'active' : ''}`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Filter size={13} style={{ color: 'var(--text-muted)' }} />
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="devices-select"
            >
              <option value="ALL">All States</option>
              {availableStates.map(st => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
          </div>

          <input
            type="text"
            placeholder="Filter process name..."
            value={procFilter}
            onChange={(e) => setProcFilter(e.target.value)}
            className="devices-search-input"
            style={{ width: '160px' }}
          />
        </div>
      </div>

      {/* 4. Active Connections Table */}
      <div className="connections-table-container">
        {error && (
          <div style={{ padding: '20px', color: 'var(--status-critical)', textAlign: 'center' }}>
            Error: {error}
          </div>
        )}

        {!error && connections.length === 0 && !loading && (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No connections matching current filters.
          </div>
        )}

        {connections.length > 0 && (
          <table className="connections-table" id="connections-data-table">
            <thead>
              <tr>
                <th className="sortable" onClick={() => handleSort('process_name')}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    PROCESS {renderSortIcon('process_name')}
                  </div>
                </th>
                <th className="sortable" onClick={() => handleSort('pid')} style={{ width: '80px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    PID {renderSortIcon('pid')}
                  </div>
                </th>
                <th className="sortable" onClick={() => handleSort('protocol')} style={{ width: '80px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    PROTO {renderSortIcon('protocol')}
                  </div>
                </th>
                <th className="sortable" onClick={() => handleSort('local_port')}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    LOCAL ENDPOINT {renderSortIcon('local_port')}
                  </div>
                </th>
                <th className="sortable" onClick={() => handleSort('remote_port')}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    REMOTE ENDPOINT {renderSortIcon('remote_port')}
                  </div>
                </th>
                <th className="sortable" onClick={() => handleSort('state')} style={{ width: '130px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    STATE {renderSortIcon('state')}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedConnections.map((c) => {
                const isSelected = selectedConn?.id === c.id;
                return (
                  <tr 
                    key={c.id} 
                    onClick={() => setSelectedConn(c)}
                    style={{ cursor: 'pointer', background: isSelected ? 'var(--bg-card-hover)' : undefined }}
                    title="Click to view detailed socket metadata"
                  >
                    <td>
                      {c.process_name ? (
                        <span className="proc-name">{c.process_name}</span>
                      ) : (
                        <span className="proc-unknown">
                          {c.pid !== null ? 'Unavailable' : 'System / Kernel'}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="mono" style={{ color: c.pid !== null ? '#94a3b8' : '#64748b' }}>
                        {c.pid ?? '—'}
                      </span>
                    </td>
                    <td>
                      <span className={`proto-badge proto-badge--${c.protocol.toLowerCase()}`}>
                        {c.protocol}
                      </span>
                    </td>
                    <td>
                      <span className="endpoint-mono">
                        {c.local_ip || '*'}:
                        <span className="endpoint-port">{c.local_port ?? '*'}</span>
                      </span>
                    </td>
                    <td>
                      <span className="endpoint-mono">
                        {c.remote_ip ? (
                          <>
                            {c.remote_ip}:
                            <span className="endpoint-port">{c.remote_port ?? '*'}</span>
                          </>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>* : *</span>
                        )}
                      </span>
                    </td>
                    <td>
                      <span className={`state-badge ${getStateBadgeClass(c.state)}`}>
                        {c.state}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer info notice */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', padding: '0 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ShieldCheck size={12} style={{ color: 'var(--status-live)' }} />
          <span>Local network metadata only. No payload inspection or remote probing performed.</span>
        </div>
        <div>
          Showing {sortedConnections.length} connection{sortedConnections.length === 1 ? '' : 's'}
        </div>
      </div>

      {/* Connection Detail Modal */}
      {selectedConn && (
        <div className="noc-modal-backdrop" onClick={() => setSelectedConn(null)}>
          <div className="noc-modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '520px' }}>
            <div className="noc-modal-header">
              <div className="noc-modal-title-group">
                <GitCommit size={18} style={{ color: 'var(--accent-cyan)' }} />
                <h3 className="noc-modal-title">Socket Connection Details</h3>
              </div>
              <button className="noc-modal-close" onClick={() => setSelectedConn(null)}>
                <X size={16} />
              </button>
            </div>

            <div className="noc-modal-body">
              <div className="noc-detail-grid">
                <div className="noc-detail-item">
                  <span className="noc-detail-label">PROCESS NAME</span>
                  <span className="noc-detail-value mono" style={{ color: 'var(--text-main)', fontWeight: 600 }}>
                    {selectedConn.process_name || 'Unavailable (Elevated/System)'}
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">PROCESS ID (PID)</span>
                  <span className="noc-detail-value mono">{selectedConn.pid ?? '—'}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">TRANSPORT PROTOCOL</span>
                  <span className="noc-detail-value mono" style={{ color: 'var(--accent-cyan)' }}>
                    {selectedConn.protocol} ({selectedConn.family || 'IPv4'})
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">SOCKET STATE</span>
                  <span className="noc-detail-value">
                    <span className={`state-badge ${getStateBadgeClass(selectedConn.state)}`}>
                      {selectedConn.state}
                    </span>
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">LOCAL ENDPOINT</span>
                  <span className="noc-detail-value mono">
                    {selectedConn.local_ip || '*'}:{selectedConn.local_port ?? '*'}
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">REMOTE ENDPOINT</span>
                  <span className="noc-detail-value mono">
                    {selectedConn.remote_ip ? `${selectedConn.remote_ip}:${selectedConn.remote_port ?? '*'}` : 'None (Listening/Unbound)'}
                  </span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">FIRST OBSERVED</span>
                  <span className="noc-detail-value mono text-muted">{selectedConn.first_observed_utc || '—'}</span>
                </div>
                <div className="noc-detail-item">
                  <span className="noc-detail-label">LAST OBSERVED</span>
                  <span className="noc-detail-value mono text-muted">{selectedConn.last_observed_utc || '—'}</span>
                </div>
                <div className="noc-detail-item" style={{ gridColumn: 'span 2' }}>
                  <span className="noc-detail-label">RUNTIME SOCKET KEY</span>
                  <span className="noc-detail-value mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                    {selectedConn.id}
                  </span>
                </div>
              </div>
            </div>

            <div className="noc-modal-footer">
              <button className="noc-btn-secondary" onClick={() => setSelectedConn(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
