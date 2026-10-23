import '../devices.css';
import React, { useState, useEffect, useCallback, useRef } from 'react';

import {
  Monitor,
  Wifi,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  Clock,
  X,
  Info,
  Loader2,
} from 'lucide-react';
import type { DeviceItem, DeviceListResponse, DiscoveryStatus, DeviceSummary } from '../types/telemetry';
import { getAuthHeaders } from '../utils/auth';

interface DevicesPageProps {
  deviceSummary?: DeviceSummary | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatRelativeTime(unixTs: number): string {
  const diffSec = Math.floor(Date.now() / 1000 - unixTs);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

function formatMac(mac: string | null): string {
  return mac ?? '—';
}

function formatHostname(hostname: string | null): string {
  return hostname ?? 'Unknown device';
}

// ─── Status Badge ────────────────────────────────────────────────────────────

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const cfg: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
    ONLINE: {
      color: 'status-badge--online',
      icon: <CheckCircle2 size={12} />,
      label: 'Online',
    },
    OFFLINE: {
      color: 'status-badge--offline',
      icon: <X size={12} />,
      label: 'Offline',
    },
    UNKNOWN: {
      color: 'status-badge--unknown',
      icon: <AlertCircle size={12} />,
      label: 'Unknown',
    },
  };
  const c = cfg[status] ?? cfg['UNKNOWN'];
  return (
    <span className={`status-badge ${c.color}`}>
      {c.icon}
      {c.label}
    </span>
  );
};

// ─── Discovery Status Bar ────────────────────────────────────────────────────

const DiscoveryStatusBar: React.FC<{
  ds: DiscoveryStatus | null;
  onScan: () => void;
  scanning: boolean;
}> = ({ ds, onScan, scanning }) => {
  const isScanning = scanning || ds?.status === 'SCANNING';
  const isUnavailable = ds?.status === 'UNAVAILABLE' || ds?.status === 'ERROR';

  return (
    <div className="devices-status-bar">
      <div className="devices-status-bar__left">
        {isScanning ? (
          <span className="devices-status-bar__scanning">
            <Loader2 size={14} className="spin" />
            Scanning {ds?.subnet ?? '…'}
          </span>
        ) : isUnavailable ? (
          <span className="devices-status-bar__error">
            <AlertCircle size={14} />
            Discovery {ds?.status?.toLowerCase()}
          </span>
        ) : (
          <span className="devices-status-bar__idle">
            <CheckCircle2 size={14} />
            {ds?.subnet ? `Subnet: ${ds.subnet}` : 'Awaiting first scan'}
            {ds?.interface ? ` · ${ds.interface}` : ''}
          </span>
        )}

        {ds?.limitation && (
          <span className="devices-status-bar__note" title={ds.limitation}>
            <Info size={12} /> {ds.limitation.slice(0, 80)}{ds.limitation.length > 80 ? '…' : ''}
          </span>
        )}
      </div>

      <div className="devices-status-bar__right">
        {ds?.last_scan_duration_seconds != null && (
          <span className="devices-meta">
            <Clock size={12} />
            Last scan: {ds.last_scan_duration_seconds.toFixed(1)}s
            {ds.devices_found_last_scan != null ? ` · ${ds.devices_found_last_scan} found` : ''}
          </span>
        )}
        <span className="devices-meta">
          Method: {ds?.discovery_method ?? 'arp_table+icmp_sweep'}
        </span>
        <button
          className="btn-rescan"
          onClick={onScan}
          disabled={isScanning}
          id="devices-rescan-btn"
        >
          <RefreshCw size={13} className={isScanning ? 'spin' : ''} />
          {isScanning ? 'Scanning…' : 'Rescan'}
        </button>
      </div>
    </div>
  );
};

// ─── Device Detail Modal ─────────────────────────────────────────────────────

const DeviceDetailModal: React.FC<{ device: DeviceItem; onClose: () => void }> = ({
  device,
  onClose,
}) => (
  <div className="modal-backdrop" onClick={onClose}>
    <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <div className="modal-title">
          <Monitor size={18} />
          Device Details
        </div>
        <button className="modal-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="modal-body">
        <div className="detail-grid">
          <DetailRow label="Status" value={<StatusBadge status={device.status} />} />
          <DetailRow label="IP Address" value={device.ip_address} mono />
          <DetailRow label="MAC Address" value={formatMac(device.mac_address)} mono />
          <DetailRow label="Hostname" value={formatHostname(device.hostname)} />
          <DetailRow label="Interface" value={device.interface_name} mono />
          <DetailRow
            label="First Seen"
            value={`${device.first_seen_utc} (${formatRelativeTime(device.first_seen)})`}
          />
          <DetailRow
            label="Last Seen"
            value={`${device.last_seen_utc} (${formatRelativeTime(device.last_seen)})`}
          />
          <DetailRow label="Missed Scans" value={String(device.missed_scan_count)} />
          <DetailRow label="Database ID" value={String(device.id)} />
        </div>
      </div>
    </div>
  </div>
);

const DetailRow: React.FC<{ label: string; value: React.ReactNode; mono?: boolean }> = ({
  label,
  value,
  mono,
}) => (
  <div className="detail-row">
    <span className="detail-label">{label}</span>
    <span className={`detail-value${mono ? ' detail-value--mono' : ''}`}>{value}</span>
  </div>
);

// ─── Sort helper ─────────────────────────────────────────────────────────────

type SortKey = 'status' | 'ip_address' | 'hostname' | 'last_seen' | 'interface_name';

function sortDevices(
  items: DeviceItem[],
  key: SortKey,
  dir: 'asc' | 'desc'
): DeviceItem[] {
  return [...items].sort((a, b) => {
    let av: string | number;
    let bv: string | number;
    switch (key) {
      case 'last_seen':
        av = a.last_seen;
        bv = b.last_seen;
        break;
      case 'hostname':
        av = formatHostname(a.hostname).toLowerCase();
        bv = formatHostname(b.hostname).toLowerCase();
        break;
      default:
        av = (a[key] ?? '').toString().toLowerCase();
        bv = (b[key] ?? '').toString().toLowerCase();
    }
    if (av < bv) return dir === 'asc' ? -1 : 1;
    if (av > bv) return dir === 'asc' ? 1 : -1;
    return 0;
  });
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export const DevicesPage: React.FC<DevicesPageProps> = ({ deviceSummary }) => {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [discoveryStatus, setDiscoveryStatus] = useState<DiscoveryStatus | null>(null);
  const [totalKnown, setTotalKnown] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ONLINE' | 'OFFLINE'>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('last_seen');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selectedDevice, setSelectedDevice] = useState<DeviceItem | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch devices list ──
  const fetchDevices = useCallback(async () => {
    try {
      let url = '/api/devices?limit=500';
      if (statusFilter !== 'ALL') url += `&status=${statusFilter}`;
      if (search) url += `&search=${encodeURIComponent(search)}`;

      const res = await fetch(url);
      if (res.ok) {
        const data: DeviceListResponse = await res.json();
        setDevices(data.items);
        setTotalKnown(data.total);
      }
    } catch (_) {/* network error — keep stale data */}
  }, [statusFilter, search]);

  // ── Fetch discovery status ──
  const fetchDiscoveryStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/devices/discovery/status');
      if (res.ok) {
        const ds: DiscoveryStatus = await res.json();
        setDiscoveryStatus(ds);
        if (ds.status !== 'SCANNING') setScanning(false);
      }
    } catch (_) {}
  }, []);

  // ── Initial load + periodic refresh ──
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await Promise.all([fetchDevices(), fetchDiscoveryStatus()]);
      setIsLoading(false);
    };
    init();

    pollRef.current = setInterval(() => {
      fetchDevices();
      fetchDiscoveryStatus();
    }, 10_000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchDevices, fetchDiscoveryStatus]);

  // ── Manual scan ──
  const handleScan = useCallback(async () => {
    if (scanning || discoveryStatus?.status === 'SCANNING') return;
    setScanning(true);
    try {
      const headers = getAuthHeaders();
      await fetch('/api/devices/scan', { method: 'POST', headers });
      // Poll status until IDLE
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await fetchDiscoveryStatus();
        await fetchDevices();
        if (attempts > 60) clearInterval(poll); // safety cap: 60 * 2s = 2min
      }, 2000);
    } catch (_) {
      setScanning(false);
    }
  }, [scanning, discoveryStatus, fetchDiscoveryStatus, fetchDevices]);

  // ── Sort & filter ──
  const sorted = sortDevices(devices, sortKey, sortDir);
  const onlineCount = devices.filter((d) => d.status === 'ONLINE').length;

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
  };

  const SortIcon: React.FC<{ col: SortKey }> = ({ col }) =>
    sortKey === col
      ? sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
      : null;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div className="page-header__left">
          <Wifi size={20} className="page-icon" />
          <div>
            <h1 className="page-title">LAN Devices</h1>
            <p className="page-subtitle">
              {onlineCount} online · {totalKnown} known
              {deviceSummary ? ` · discovery ${deviceSummary.discovery_status.toLowerCase()}` : ''}
            </p>
          </div>
        </div>
      </div>

      {/* Discovery status bar */}
      <DiscoveryStatusBar
        ds={discoveryStatus}
        onScan={handleScan}
        scanning={scanning}
      />

      {/* UNAVAILABLE / ERROR notice */}
      {(discoveryStatus?.status === 'UNAVAILABLE' || discoveryStatus?.status === 'ERROR') && (
        <div className="devices-alert-banner">
          <AlertCircle size={16} />
          <div>
            <strong>Discovery {discoveryStatus.status.toLowerCase()}:</strong>{' '}
            {discoveryStatus.error ?? discoveryStatus.limitation ?? 'Unknown error.'}
            <br />
            <span className="devices-alert-sub">
              Other NetWatch features (telemetry, alerts, latency) continue to function normally.
            </span>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="devices-toolbar">
        <div className="search-box">
          <Search size={14} className="search-icon" />
          <input
            id="devices-search"
            type="text"
            className="search-input"
            placeholder="Search IP, MAC, or hostname…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="search-clear" onClick={() => setSearch('')}>
              <X size={12} />
            </button>
          )}
        </div>

        <div className="filter-tabs">
          {(['ALL', 'ONLINE', 'OFFLINE'] as const).map((s) => (
            <button
              key={s}
              className={`filter-tab${statusFilter === s ? ' filter-tab--active' : ''}`}
              onClick={() => setStatusFilter(s)}
              id={`devices-filter-${s.toLowerCase()}`}
            >
              {s === 'ALL' ? `All (${totalKnown})` : s === 'ONLINE' ? `Online (${onlineCount})` : `Offline (${totalKnown - onlineCount})`}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="table-wrapper">
        {isLoading ? (
          <div className="table-loading">
            <Loader2 size={24} className="spin" />
            <span>Loading devices…</span>
          </div>
        ) : sorted.length === 0 ? (
          <div className="table-empty">
            <Monitor size={40} className="table-empty__icon" />
            <p className="table-empty__title">No devices found</p>
            <p className="table-empty__sub">
              {devices.length === 0
                ? 'Click Rescan to discover LAN devices.'
                : 'No devices match your current filter.'}
            </p>
          </div>
        ) : (
          <table className="devices-table" id="devices-table">
            <thead>
              <tr>
                <th onClick={() => toggleSort('status')} className="sortable">
                  STATUS <SortIcon col="status" />
                </th>
                <th onClick={() => toggleSort('hostname')} className="sortable">
                  DEVICE <SortIcon col="hostname" />
                </th>
                <th onClick={() => toggleSort('ip_address')} className="sortable">
                  IP ADDRESS <SortIcon col="ip_address" />
                </th>
                <th>MAC ADDRESS</th>
                <th onClick={() => toggleSort('interface_name')} className="sortable">
                  INTERFACE <SortIcon col="interface_name" />
                </th>
                <th onClick={() => toggleSort('last_seen')} className="sortable">
                  LAST SEEN <SortIcon col="last_seen" />
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((d) => (
                <tr
                  key={d.id}
                  className={`devices-row devices-row--${d.status.toLowerCase()}${
                    selectedDevice?.id === d.id ? ' devices-row--selected' : ''
                  }`}
                  onClick={() => setSelectedDevice(d)}
                  id={`device-row-${d.id}`}
                >
                  <td>
                    <StatusBadge status={d.status} />
                  </td>
                  <td className="device-name-cell">
                    <Monitor size={14} className={`device-icon device-icon--${d.status.toLowerCase()}`} />
                    <span className={!d.hostname ? 'text-muted' : ''}>
                      {formatHostname(d.hostname)}
                    </span>
                  </td>
                  <td className="mono">{d.ip_address}</td>
                  <td className="mono text-muted-sm">{formatMac(d.mac_address)}</td>
                  <td className="mono">{d.interface_name}</td>
                  <td className="text-muted-sm">{formatRelativeTime(d.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {sorted.length > 0 && (
        <p className="table-footer">
          Showing {sorted.length} of {totalKnown} known device{totalKnown !== 1 ? 's' : ''}
          {search ? ` · filtered by "${search}"` : ''}
        </p>
      )}

      {/* Device detail modal */}
      {selectedDevice && (
        <DeviceDetailModal
          device={selectedDevice}
          onClose={() => setSelectedDevice(null)}
        />
      )}
    </div>
  );
};
