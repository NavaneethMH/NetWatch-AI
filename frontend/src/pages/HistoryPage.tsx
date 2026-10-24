import React, { useState, useEffect } from 'react';
import { apiUrl } from '../utils/api';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell, ReferenceLine,
} from 'recharts';
import type {
  AnalyticsCoverage, TimeSeriesResponse, AnalyticsReport,
  NetworkHistoryItem, SystemHistoryItem,
} from '../types/telemetry';
import { formatBytes } from '../utils/formatters';
import {
  Database, Clock, TrendingUp, Activity, Wifi, Cpu,
  AlertTriangle, Network, RefreshCw, BarChart2, Table,
} from 'lucide-react';

// ─── Constants ────────────────────────────────────────────────────────────────

const RANGE_OPTIONS = [
  { key: '5m', label: '5 min' },
  { key: '15m', label: '15 min' },
  { key: '1h', label: '1 hour' },
  { key: '6h', label: '6 hours' },
  { key: '24h', label: '24 hours' },
  { key: '7d', label: '7 days' },
  { key: 'all', label: 'All data' },
];

const TABLE_LABELS: Record<string, string> = {
  system_metrics: 'System Telemetry',
  network_metrics: 'Network Throughput',
  interface_metrics: 'Interface Metrics',
  latency_metrics: 'Latency Probes',
  protocol_metrics: 'Protocol Windows',
  alerts: 'Alert Events',
  devices: 'Known Devices',
};

// ─── Color palette ─────────────────────────────────────────────────────────

const C = {
  dl:       '#10b981',
  ul:       '#00d4ff',
  cpu:      '#a78bfa',
  mem:      '#f59e0b',
  lat:      '#fb923c',
  loss:     '#ef4444',
  pps:      '#3b82f6',
  tcp:      '#10b981',
  udp:      '#00d4ff',
  icmp:     '#a78bfa',
  dns:      '#f59e0b',
  ipv4:     '#3b82f6',
  ipv6:     '#ec4899',
  grid:     'rgba(255,255,255,0.04)',
  axis:     '#374151',
  tooltip:  '#131924',
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt2(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toFixed(2);
}
function labelTs(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function shortTs(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleString([], {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface ChartWrapProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}
const ChartWrap: React.FC<ChartWrapProps> = ({ title, icon, children, className }) => (
  <div className={`analytics-chart-card ${className ?? ''}`}>
    <div className="analytics-chart-header">
      <span className="analytics-chart-icon">{icon}</span>
      <span className="analytics-chart-title">{title}</span>
    </div>
    <div className="analytics-chart-body">{children}</div>
  </div>
);

const CustomTooltipBase: React.FC<{ active?: boolean; payload?: any[]; label?: any; rows: { label: string; key: string; unit?: string; color: string }[] }> = ({ active, payload, label, rows }) => {
  if (!active || !payload?.length) return null;
  const map: Record<string, number | null> = {};
  payload.forEach((p: any) => { map[p.dataKey] = p.value; });
  return (
    <div className="analytics-tooltip">
      <div className="analytics-tooltip-time">{typeof label === 'number' ? shortTs(label) : label}</div>
      {rows.map(r => (
        <div key={r.key} className="analytics-tooltip-row">
          <span className="analytics-tooltip-dot" style={{ background: r.color }} />
          <span className="analytics-tooltip-label">{r.label}</span>
          <span className="analytics-tooltip-value">
            {map[r.key] != null ? `${fmt2(map[r.key])}${r.unit ?? ''}` : '—'}
          </span>
        </div>
      ))}
    </div>
  );
};

// ─── Coverage Card ────────────────────────────────────────────────────────────

const CoveragePanel: React.FC<{ coverage: AnalyticsCoverage | null; loading: boolean }> = ({ coverage, loading }) => (
  <div className="analytics-coverage-panel">
    <div className="analytics-section-header">
      <Database size={14} />
      <span>DATA COVERAGE</span>
      {loading && <span className="analytics-spinner" />}
    </div>
    {coverage && (
      <div className="analytics-coverage-grid">
        {coverage.tables.map(t => (
          <div key={t.table} className="analytics-coverage-card">
            <div className="analytics-cov-name">{TABLE_LABELS[t.table] ?? t.table}</div>
            <div className="analytics-cov-count mono">{t.row_count.toLocaleString()} rows</div>
            <div className="analytics-cov-span text-muted">
              {t.span_human ? `Span: ${t.span_human}` : 'No data'}
            </div>
            <div className="analytics-cov-ret text-dim">
              Retention: {t.retention_human ?? 'unlimited'}
            </div>
            {t.newest_utc && (
              <div className="analytics-cov-newest text-dim">
                Latest: {t.newest_utc}
              </div>
            )}
          </div>
        ))}
      </div>
    )}
  </div>
);

// ─── Report Stats Row ────────────────────────────────────────────────────────

const StatKPI: React.FC<{ label: string; value: string; sub?: string; color?: string }> = ({ label, value, sub, color }) => (
  <div className="analytics-kpi">
    <div className="analytics-kpi-label">{label}</div>
    <div className="analytics-kpi-value" style={color ? { color } : undefined}>{value}</div>
    {sub && <div className="analytics-kpi-sub">{sub}</div>}
  </div>
);

// ─── Pie legend ───────────────────────────────────────────────────────────────

const RADIAN = Math.PI / 180;
const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }: any) => {
  if (percent < 0.05) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.6;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={10} fontWeight={600}>
      {name}
    </text>
  );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

type SubPage = 'charts' | 'report' | 'audit';

export const HistoryPage: React.FC = () => {
  const [range, setRange] = useState('1h');
  const [subPage, setSubPage] = useState<SubPage>('charts');
  const [coverage, setCoverage] = useState<AnalyticsCoverage | null>(null);
  const [timeseries, setTimeseries] = useState<TimeSeriesResponse | null>(null);
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [auditTab, setAuditTab] = useState<'network' | 'system'>('network');
  const [auditRows, setAuditRows] = useState<(NetworkHistoryItem | SystemHistoryItem)[]>([]);
  const [loading, setLoading] = useState(false);
  const [tsLoading, setTsLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  // Fetch coverage once on mount
  useEffect(() => {
    fetch(apiUrl('/api/analytics/coverage'))
      .then(r => r.json())
      .then(setCoverage)
      .catch(console.error);
  }, []);

  // Fetch time-series when range changes
  useEffect(() => {
    if (subPage !== 'charts') return;
    setTsLoading(true);
    fetch(apiUrl(`/api/analytics/timeseries?range=${range}`))
      .then(r => r.json())
      .then(setTimeseries)
      .catch(console.error)
      .finally(() => setTsLoading(false));
  }, [range, subPage]);

  // Fetch report when range changes
  useEffect(() => {
    if (subPage !== 'report') return;
    setReportLoading(true);
    fetch(apiUrl(`/api/analytics/report?range=${range}`))
      .then(r => r.json())
      .then(setReport)
      .catch(console.error)
      .finally(() => setReportLoading(false));
  }, [range, subPage]);

  // Fetch audit rows
  useEffect(() => {
    if (subPage !== 'audit') return;
    setLoading(true);
    const ep = auditTab === 'network'
      ? apiUrl('/api/network/history?limit=200&order=desc')
      : apiUrl('/api/system/history?limit=200&order=desc');
    fetch(ep)
      .then(r => r.json())
      .then(d => setAuditRows(d.items || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [subPage, auditTab]);

  const pts = timeseries?.points ?? [];

  // Protocol pie data
  const protoPie = report ? [
    { name: 'TCP',  value: report.tcp_share_pct ?? 0,  fill: C.tcp  },
    { name: 'UDP',  value: report.udp_share_pct ?? 0,  fill: C.udp  },
    { name: 'ICMP', value: report.icmp_share_pct ?? 0, fill: C.icmp },
    { name: 'DNS',  value: report.dns_share_pct ?? 0,  fill: C.dns  },
    { name: 'Other', value: Math.max(0,
        100 - (report.tcp_share_pct ?? 0)
            - (report.udp_share_pct ?? 0)
            - (report.icmp_share_pct ?? 0)
            - (report.dns_share_pct ?? 0)), fill: '#6b7280' },
  ].filter(d => d.value > 0) : [];

  const ipPie = report ? [
    { name: 'IPv4', value: report.ipv4_share_pct ?? 0, fill: C.ipv4 },
    { name: 'IPv6', value: report.ipv6_share_pct ?? 0, fill: C.ipv6 },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="noc-page-container analytics-page">

      {/* ── Top toolbar ── */}
      <div className="analytics-toolbar">
        <div className="analytics-toolbar-left">
          <div className="analytics-tab-group">
            {(['charts', 'report', 'audit'] as SubPage[]).map(t => (
              <button
                key={t}
                id={`analytics-tab-${t}`}
                onClick={() => setSubPage(t)}
                className={`analytics-tab-btn ${subPage === t ? 'active' : ''}`}
              >
                {t === 'charts' && <BarChart2 size={12} />}
                {t === 'report' && <TrendingUp size={12} />}
                {t === 'audit' && <Table size={12} />}
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="analytics-toolbar-right">
          {/* Coverage summary badges */}
          {coverage && (
            <div className="analytics-cov-badges">
              {coverage.tables.slice(0, 3).map(t => (
                <span key={t.table} className="analytics-cov-badge" title={t.table}>
                  <Database size={9} />
                  {t.row_count.toLocaleString()}
                </span>
              ))}
            </div>
          )}

          {/* Range selector */}
          <div className="analytics-range-group">
            {RANGE_OPTIONS.map(r => (
              <button
                key={r.key}
                id={`analytics-range-${r.key}`}
                onClick={() => setRange(r.key)}
                className={`analytics-range-btn ${range === r.key ? 'active' : ''}`}
              >
                {r.label}
              </button>
            ))}
          </div>

          {/* Refresh */}
          <button
            id="analytics-refresh"
            className="noc-btn-secondary"
            onClick={() => {
              const ts = Date.now();
              if (subPage === 'charts') {
                setTsLoading(true);
                fetch(apiUrl(`/api/analytics/timeseries?range=${range}&_t=${ts}`))
                  .then(r => r.json()).then(setTimeseries).finally(() => setTsLoading(false));
              } else if (subPage === 'report') {
                setReportLoading(true);
                fetch(apiUrl(`/api/analytics/report?range=${range}&_t=${ts}`))
                  .then(r => r.json()).then(setReport).finally(() => setReportLoading(false));
              }
            }}
            title="Refresh"
          >
            <RefreshCw size={12} className={tsLoading || reportLoading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* ── Coverage row (always visible) ── */}
      <CoveragePanel coverage={coverage} loading={false} />

      {/* ═══════════════════════════════════════════════════════════════════
           SUB-PAGE: CHARTS
         ═══════════════════════════════════════════════════════════════════ */}
      {subPage === 'charts' && (
        <div className="analytics-charts-grid">
          {tsLoading && (
            <div className="analytics-loading-overlay">
              <RefreshCw size={18} className="spin" />
              <span>Fetching {pts.length > 0 ? 'updated' : ''} telemetry…</span>
            </div>
          )}

          {/* 1. Network Throughput */}
          <ChartWrap title="Network Throughput" icon={<Wifi size={13} />} className="span-2">
            {pts.length === 0 ? (
              <div className="analytics-empty">No network data in selected range</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={pts} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="dlGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.dl} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={C.dl} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="ulGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.ul} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={C.ul} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="bucket_ts" tickFormatter={labelTs} tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}M`} width={38} />
                  <Tooltip content={<CustomTooltipBase rows={[
                    { label: '↓ DL', key: 'download_mbps', unit: ' Mbps', color: C.dl },
                    { label: '↑ UL', key: 'upload_mbps', unit: ' Mbps', color: C.ul },
                  ]} />} />
                  <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
                  <Area type="monotone" dataKey="download_mbps" name="Download" stroke={C.dl} fill="url(#dlGrad)" strokeWidth={1.5} dot={false} connectNulls />
                  <Area type="monotone" dataKey="upload_mbps" name="Upload" stroke={C.ul} fill="url(#ulGrad)" strokeWidth={1.5} dot={false} connectNulls />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </ChartWrap>

          {/* 2. CPU & Memory */}
          <ChartWrap title="CPU & Memory Usage" icon={<Cpu size={13} />}>
            {pts.length === 0 ? (
              <div className="analytics-empty">No system data in range</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={pts} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="bucket_ts" tickFormatter={labelTs} tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={v => `${v}%`} width={36} />
                  <Tooltip content={<CustomTooltipBase rows={[
                    { label: 'CPU', key: 'cpu_percent', unit: '%', color: C.cpu },
                    { label: 'RAM', key: 'memory_percent', unit: '%', color: C.mem },
                  ]} />} />
                  <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
                  <ReferenceLine y={90} stroke={C.loss} strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="cpu_percent" name="CPU %" stroke={C.cpu} strokeWidth={1.5} dot={false} connectNulls />
                  <Line type="monotone" dataKey="memory_percent" name="RAM %" stroke={C.mem} strokeWidth={1.5} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartWrap>

          {/* 3. Latency */}
          <ChartWrap title="Latency & Packet Loss" icon={<Activity size={13} />}>
            {pts.length === 0 ? (
              <div className="analytics-empty">No latency data in range</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={pts} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="bucket_ts" tickFormatter={labelTs} tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis yAxisId="ms" tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}ms`} width={42} />
                  <YAxis yAxisId="loss" orientation="right" tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} width={32} />
                  <Tooltip content={<CustomTooltipBase rows={[
                    { label: 'Avg RTT', key: 'latency_avg_ms', unit: 'ms', color: C.lat },
                    { label: 'Max RTT', key: 'latency_max_ms', unit: 'ms', color: C.mem },
                    { label: 'Loss',    key: 'packet_loss_percent', unit: '%', color: C.loss },
                  ]} />} />
                  <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
                  <Line yAxisId="ms" type="monotone" dataKey="latency_avg_ms" name="Avg RTT (ms)" stroke={C.lat} strokeWidth={1.5} dot={false} connectNulls />
                  <Line yAxisId="ms" type="monotone" dataKey="latency_max_ms" name="Max RTT (ms)" stroke={C.mem} strokeWidth={1} dot={false} strokeDasharray="3 3" connectNulls />
                  <Line yAxisId="loss" type="monotone" dataKey="packet_loss_percent" name="Loss %" stroke={C.loss} strokeWidth={1.5} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ChartWrap>

          {/* 4. Protocol PPS */}
          <ChartWrap title="Packets per Second (PPS)" icon={<Network size={13} />}>
            {pts.length === 0 ? (
              <div className="analytics-empty">No protocol data in range</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={pts} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="ppsGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.pps} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={C.pps} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="bucket_ts" tickFormatter={labelTs} tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={40} />
                  <YAxis tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}`} width={36} />
                  <Tooltip content={<CustomTooltipBase rows={[
                    { label: 'PPS', key: 'pps', unit: ' pps', color: C.pps },
                  ]} />} />
                  <Area type="monotone" dataKey="pps" name="PPS" stroke={C.pps} fill="url(#ppsGrad)" strokeWidth={1.5} dot={false} connectNulls />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </ChartWrap>

          {/* 5. Protocol mix stacked bar */}
          <ChartWrap title="Transport Protocol Mix" icon={<Network size={13} />} className="span-2">
            {pts.filter(p => (p.tcp_packets ?? 0) > 0 || (p.udp_packets ?? 0) > 0).length === 0 ? (
              <div className="analytics-empty">No packet classification data in range</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={pts} margin={{ top: 4, right: 12, left: 0, bottom: 0 }} barSize={8}>
                  <CartesianGrid stroke={C.grid} vertical={false} />
                  <XAxis dataKey="bucket_ts" tickFormatter={labelTs} tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={60} />
                  <YAxis tick={{ fill: C.axis, fontSize: 10 }} tickLine={false} axisLine={false} width={36} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
                  <Bar dataKey="tcp_packets" name="TCP" stackId="a" fill={C.tcp} />
                  <Bar dataKey="udp_packets" name="UDP" stackId="a" fill={C.udp} />
                  <Bar dataKey="icmp_packets" name="ICMP" stackId="a" fill={C.icmp} />
                  <Bar dataKey="dns_packets" name="DNS" stackId="a" fill={C.dns} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartWrap>

        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
           SUB-PAGE: REPORT
         ═══════════════════════════════════════════════════════════════════ */}
      {subPage === 'report' && (
        <div className="analytics-report-wrap">
          {reportLoading ? (
            <div className="analytics-loading-overlay">
              <RefreshCw size={18} className="spin" />
              <span>Aggregating statistics…</span>
            </div>
          ) : report ? (
            <>
              {/* Window banner */}
              <div className="analytics-window-banner">
                <Clock size={13} />
                <span>Window: <strong>{report.window_human}</strong></span>
                <span className="text-dim">
                  {report.from_utc} → {report.to_utc}
                </span>
              </div>

              {/* KPI row 1: Network */}
              <div className="analytics-report-section">
                <div className="analytics-section-header">
                  <Wifi size={13} />
                  <span>NETWORK THROUGHPUT</span>
                </div>
                <div className="analytics-kpi-row">
                  <StatKPI label="Download avg" value={`${fmt2(report.download_mbps?.avg)} Mbps`} sub={`max ${fmt2(report.download_mbps?.max)} Mbps`} color={C.dl} />
                  <StatKPI label="Download p95" value={`${fmt2(report.download_mbps?.p95)} Mbps`} sub={`${report.download_mbps?.sample_count ?? 0} samples`} color={C.dl} />
                  <StatKPI label="Upload avg" value={`${fmt2(report.upload_mbps?.avg)} Mbps`} sub={`max ${fmt2(report.upload_mbps?.max)} Mbps`} color={C.ul} />
                  <StatKPI label="Upload p95" value={`${fmt2(report.upload_mbps?.p95)} Mbps`} sub={`${report.upload_mbps?.sample_count ?? 0} samples`} color={C.ul} />
                </div>
              </div>

              {/* KPI row 2: System */}
              <div className="analytics-report-section">
                <div className="analytics-section-header">
                  <Cpu size={13} />
                  <span>SYSTEM RESOURCES</span>
                </div>
                <div className="analytics-kpi-row">
                  <StatKPI label="CPU avg" value={`${fmt2(report.cpu_percent?.avg)}%`} sub={`max ${fmt2(report.cpu_percent?.max)}%`} color={C.cpu} />
                  <StatKPI label="CPU p95" value={`${fmt2(report.cpu_percent?.p95)}%`} sub={`${report.cpu_percent?.sample_count ?? 0} samples`} color={C.cpu} />
                  <StatKPI label="RAM avg" value={`${fmt2(report.memory_percent?.avg)}%`} sub={`max ${fmt2(report.memory_percent?.max)}%`} color={C.mem} />
                  <StatKPI label="RAM p95" value={`${fmt2(report.memory_percent?.p95)}%`} sub={`${report.memory_percent?.sample_count ?? 0} samples`} color={C.mem} />
                </div>
              </div>

              {/* KPI row 3: Latency */}
              <div className="analytics-report-section">
                <div className="analytics-section-header">
                  <Activity size={13} />
                  <span>LATENCY & REACHABILITY</span>
                </div>
                <div className="analytics-kpi-row">
                  <StatKPI label="RTT avg" value={`${fmt2(report.latency_avg_ms?.avg)} ms`} sub={`min ${fmt2(report.latency_avg_ms?.min)} ms`} color={C.lat} />
                  <StatKPI label="RTT p95" value={`${fmt2(report.latency_avg_ms?.p95)} ms`} sub={`max ${fmt2(report.latency_avg_ms?.max)} ms`} color={C.lat} />
                  <StatKPI label="Pkt loss avg" value={`${fmt2(report.packet_loss_percent?.avg)}%`} sub={`p95 ${fmt2(report.packet_loss_percent?.p95)}%`} color={C.loss} />
                  <StatKPI label="Probes" value={`${report.latency_avg_ms?.sample_count ?? 0}`} sub="recorded" />
                </div>
              </div>

              {/* KPI row 4: Protocol */}
              <div className="analytics-report-section">
                <div className="analytics-section-header">
                  <Network size={13} />
                  <span>PROTOCOL ANALYTICS</span>
                </div>
                <div className="analytics-proto-report">
                  <div className="analytics-kpi-row" style={{ flex: 1 }}>
                    <StatKPI label="Total packets" value={report.total_packets.toLocaleString()} color={C.pps} />
                    <StatKPI label="PPS avg" value={`${fmt2(report.pps?.avg)}`} sub={`max ${fmt2(report.pps?.max)} pps`} color={C.pps} />
                    <StatKPI label="TCP share" value={`${fmt2(report.tcp_share_pct)}%`} color={C.tcp} />
                    <StatKPI label="UDP share" value={`${fmt2(report.udp_share_pct)}%`} color={C.udp} />
                    <StatKPI label="DNS share" value={`${fmt2(report.dns_share_pct)}%`} color={C.dns} />
                    <StatKPI label="ICMP share" value={`${fmt2(report.icmp_share_pct)}%`} color={C.icmp} />
                  </div>

                  {/* Mini pie charts */}
                  <div className="analytics-pie-row">
                    {protoPie.length > 0 && (
                      <div className="analytics-pie-wrap">
                        <div className="analytics-pie-title">Transport</div>
                        <ResponsiveContainer width={160} height={140}>
                          <PieChart>
                            <Pie data={protoPie} cx="50%" cy="50%" innerRadius={38} outerRadius={60}
                              dataKey="value" labelLine={false} label={renderPieLabel}>
                              {protoPie.map((e, i) => <Cell key={i} fill={e.fill} />)}
                            </Pie>
                            <Tooltip formatter={(v: any) => [`${fmt2(v)}%`, '']} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    {ipPie.length > 0 && (
                      <div className="analytics-pie-wrap">
                        <div className="analytics-pie-title">IP Version</div>
                        <ResponsiveContainer width={160} height={140}>
                          <PieChart>
                            <Pie data={ipPie} cx="50%" cy="50%" innerRadius={38} outerRadius={60}
                              dataKey="value" labelLine={false} label={renderPieLabel}>
                              {ipPie.map((e, i) => <Cell key={i} fill={e.fill} />)}
                            </Pie>
                            <Tooltip formatter={(v: any) => [`${fmt2(v)}%`, '']} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* KPI row 5: Alerts */}
              <div className="analytics-report-section">
                <div className="analytics-section-header">
                  <AlertTriangle size={13} />
                  <span>ALERT ACTIVITY</span>
                </div>
                <div className="analytics-kpi-row">
                  <StatKPI label="Total alerts" value={`${report.total_alerts}`} />
                  <StatKPI label="Critical" value={`${report.critical_alerts}`} color={C.loss} />
                  <StatKPI label="Warning" value={`${report.warning_alerts}`} color={C.mem} />
                  <StatKPI label="Info" value={`${report.info_alerts}`} color="#60a5fa" />
                </div>
              </div>
            </>
          ) : (
            <div className="analytics-empty" style={{ padding: 40 }}>
              Select a time range and the report will load automatically.
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
           SUB-PAGE: AUDIT TABLE
         ═══════════════════════════════════════════════════════════════════ */}
      {subPage === 'audit' && (
        <div className="noc-panel">
          <div className="noc-panel-header">
            <div className="noc-panel-title-group">
              <h3 className="noc-panel-title">SQLITE TELEMETRY AUDIT TRAIL</h3>
              <span className="noc-panel-subtitle">
                Table: <span className="mono text-main">
                  {auditTab === 'network' ? 'network_metrics' : 'system_metrics'}
                </span>
              </span>
            </div>
            <div className="noc-panel-actions">
              <div className="noc-pill-group">
                <button
                  id="audit-tab-network"
                  onClick={() => setAuditTab('network')}
                  className={`noc-pill-btn ${auditTab === 'network' ? 'active' : ''}`}
                >Network</button>
                <button
                  id="audit-tab-system"
                  onClick={() => setAuditTab('system')}
                  className={`noc-pill-btn ${auditTab === 'system' ? 'active' : ''}`}
                >System</button>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="noc-empty-state"><span>Loading audit trail…</span></div>
          ) : auditRows.length === 0 ? (
            <div className="noc-empty-state">
              <span className="noc-empty-title">No rows yet</span>
              <span className="noc-empty-desc">Storage worker persists every 2s.</span>
            </div>
          ) : auditTab === 'network' ? (
            <div className="noc-table-wrap">
              <table className="noc-table">
                <thead>
                  <tr>
                    <th>ID</th><th>SAMPLE ID</th><th>UTC TIMESTAMP</th>
                    <th>STATUS</th><th>↓ DL</th><th>↑ UL</th>
                    <th>INTERVAL</th><th>BYTES RECV</th><th>BYTES SENT</th>
                  </tr>
                </thead>
                <tbody>
                  {(auditRows as NetworkHistoryItem[]).map(row => (
                    <tr key={row.id}>
                      <td className="mono text-dim">{row.id}</td>
                      <td className="mono color-cyan" style={{ fontSize: 11 }}>{row.sample_id.substring(0, 8)}…</td>
                      <td className="mono text-muted" style={{ fontSize: 11 }}>{row.timestamp_utc}</td>
                      <td>{row.status === 'LIVE'
                        ? <span className="noc-tag-live">LIVE</span>
                        : <span className="noc-tag-warning">{row.status}</span>}
                      </td>
                      <td className="mono color-dl">{row.download_mbps != null ? `${row.download_mbps.toFixed(3)} Mbps` : <span className="text-dim">NULL</span>}</td>
                      <td className="mono color-ul">{row.upload_mbps != null ? `${row.upload_mbps.toFixed(3)} Mbps` : <span className="text-dim">NULL</span>}</td>
                      <td className="mono text-dim">{row.elapsed_seconds ? `${row.elapsed_seconds}s` : '—'}</td>
                      <td className="mono text-muted">{formatBytes(row.bytes_recv)}</td>
                      <td className="mono text-muted">{formatBytes(row.bytes_sent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="noc-table-wrap">
              <table className="noc-table">
                <thead>
                  <tr>
                    <th>ID</th><th>SAMPLE ID</th><th>UTC TIMESTAMP</th>
                    <th>STATUS</th><th>CPU %</th><th>RAM %</th>
                    <th>RAM USED</th><th>DISK %</th><th>UPTIME</th>
                  </tr>
                </thead>
                <tbody>
                  {(auditRows as SystemHistoryItem[]).map(row => (
                    <tr key={row.id}>
                      <td className="mono text-dim">{row.id}</td>
                      <td className="mono color-cyan" style={{ fontSize: 11 }}>{row.sample_id.substring(0, 8)}…</td>
                      <td className="mono text-muted" style={{ fontSize: 11 }}>{row.timestamp_utc}</td>
                      <td><span className={row.collector_status === 'OK' ? 'noc-tag-live' : 'noc-tag-warning'}>{row.collector_status}</span></td>
                      <td className="mono text-main">{row.cpu_percent != null ? `${row.cpu_percent}%` : <span className="text-dim">NULL</span>}</td>
                      <td className="mono color-cyan">{row.memory_percent != null ? `${row.memory_percent}%` : <span className="text-dim">NULL</span>}</td>
                      <td className="mono text-muted">{row.memory_used_bytes ? formatBytes(row.memory_used_bytes) : '—'}</td>
                      <td className="mono text-main">{row.disk_percent != null ? `${row.disk_percent}%` : '—'}</td>
                      <td className="mono text-dim">{row.uptime_seconds ? `${Math.floor(row.uptime_seconds)}s` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
