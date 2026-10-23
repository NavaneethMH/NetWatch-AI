import React from 'react';
import type { NetworkTotals } from '../../types/telemetry';
import { formatBytes } from '../../utils/formatters';
import { ArrowDownLeft, ArrowUpRight, Radio, AlertOctagon } from 'lucide-react';

interface NetworkTotalsGridProps {
  totals: NetworkTotals | null | undefined;
}

export const NetworkTotalsGrid: React.FC<NetworkTotalsGridProps> = ({ totals }) => {
  return (
    <div className="noc-panel">
      <div className="noc-panel-header">
        <div className="noc-panel-title-group">
          <h3 className="noc-panel-title">NETWORK TRAFFIC TOTALS</h3>
          <span className="noc-panel-subtitle">Cumulative host socket counters since interface startup</span>
        </div>
      </div>

      <div className="noc-totals-grid">
        <div className="noc-total-card">
          <div className="noc-total-header">
            <ArrowDownLeft size={13} className="color-dl" />
            <span>TOTAL RECEIVED</span>
          </div>
          <div className="noc-total-val mono">
            {totals ? formatBytes(totals.bytes_recv) : '—'}
          </div>
          <div className="noc-total-sub mono text-dim">
            {totals ? `${totals.packets_recv.toLocaleString()} pkts` : '—'}
          </div>
        </div>

        <div className="noc-total-card">
          <div className="noc-total-header">
            <ArrowUpRight size={13} className="color-ul" />
            <span>TOTAL SENT</span>
          </div>
          <div className="noc-total-val mono">
            {totals ? formatBytes(totals.bytes_sent) : '—'}
          </div>
          <div className="noc-total-sub mono text-dim">
            {totals ? `${totals.packets_sent.toLocaleString()} pkts` : '—'}
          </div>
        </div>

        <div className="noc-total-card">
          <div className="noc-total-header">
            <Radio size={13} color="#a78bfa" />
            <span>AGGREGATE PACKETS</span>
          </div>
          <div className="noc-total-val mono">
            {totals ? (totals.packets_recv + totals.packets_sent).toLocaleString() : '—'}
          </div>
          <div className="noc-total-sub mono text-dim">
            In: {totals?.packets_recv.toLocaleString() ?? '—'} | Out: {totals?.packets_sent.toLocaleString() ?? '—'}
          </div>
        </div>

        <div className="noc-total-card">
          <div className="noc-total-header">
            <AlertOctagon size={13} color={totals && (totals.dropin + totals.errin > 0) ? 'var(--status-critical)' : '#10b981'} />
            <span>DROPS & ERRORS</span>
          </div>
          <div className="noc-total-val mono" style={{ color: totals && (totals.dropin + totals.errin > 0) ? 'var(--status-critical)' : 'var(--text-main)' }}>
            {totals ? (totals.dropin + totals.dropout + totals.errin + totals.errout).toLocaleString() : '—'}
          </div>
          <div className="noc-total-sub mono text-dim">
            Drops: {totals ? totals.dropin + totals.dropout : '—'} | Errs: {totals ? totals.errin + totals.errout : '—'}
          </div>
        </div>
      </div>
    </div>
  );
};
