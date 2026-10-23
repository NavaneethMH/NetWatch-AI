import React, { useState } from 'react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip 
} from 'recharts';
import { RefreshCw } from 'lucide-react';
import type { ChartDataPoint } from '../../types/telemetry';

export type TimeRangeOption = 'LIVE' | '5m' | '15m' | '1h';

interface ThroughputChartProps {
  data: ChartDataPoint[];
  selectedRange: TimeRangeOption;
  onRangeChange: (range: TimeRangeOption) => void;
  isLoading?: boolean;
}

export const ThroughputChart: React.FC<ThroughputChartProps> = ({
  data,
  selectedRange,
  onRangeChange,
  isLoading = false
}) => {
  const [hoveredPoint, setHoveredPoint] = useState<ChartDataPoint | null>(null);

  return (
    <div className="noc-panel noc-chart-panel">
      <div className="noc-panel-header">
        <div className="noc-panel-title-group">
          <h3 className="noc-panel-title">NETWORK THROUGHPUT</h3>
          <span className="noc-panel-subtitle">
            {selectedRange === 'LIVE' ? 'Real-time WebSocket stream deltas' : `Historical archive (${selectedRange})`}
          </span>
        </div>

        <div className="noc-panel-actions">
          <div className="noc-chart-legend">
            <div className="noc-legend-item">
              <span className="noc-legend-dot bg-dl"></span>
              <span>Download</span>
            </div>
            <div className="noc-legend-item">
              <span className="noc-legend-dot bg-ul"></span>
              <span>Upload</span>
            </div>
          </div>

          <div className="noc-pill-group">
            {(['LIVE', '5m', '15m', '1h'] as TimeRangeOption[]).map(option => (
              <button
                key={option}
                onClick={() => onRangeChange(option)}
                className={`noc-pill-btn ${selectedRange === option ? 'active' : ''}`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="noc-chart-canvas">
        {isLoading ? (
          <div className="noc-empty-state">
            <RefreshCw size={20} className="animate-spin text-dim" />
            <span>Querying telemetry data...</span>
          </div>
        ) : data.length === 0 ? (
          <div className="noc-empty-state">
            <span className="noc-empty-title">Waiting for first telemetry sample</span>
            <span className="noc-empty-desc">Telemetry engine will plot samples as valid counter deltas arrive.</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart 
              data={data} 
              margin={{ top: 12, right: 12, left: -16, bottom: 0 }}
              onMouseMove={(e: any) => {
                if (e && e.activePayload && e.activePayload.length) {
                  setHoveredPoint(e.activePayload[0].payload);
                }
              }}
              onMouseLeave={() => setHoveredPoint(null)}
            >
              <defs>
                <linearGradient id="nocDlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="nocUlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#00d4ff" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="time"
                stroke="var(--text-dim)"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: 'var(--border-subtle)' }}
                dy={6}
              />
              <YAxis
                stroke="var(--text-dim)"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: 'var(--border-subtle)' }}
                tickFormatter={(v) => `${v} Mbps`}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '4px',
                  fontSize: '12px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
                }}
                itemStyle={{ color: 'var(--text-main)' }}
                formatter={(val: any) => [val !== null ? `${Number(val).toFixed(3)} Mbps` : 'NULL (WARMUP / GAP)']}
              />
              <Area
                type="monotone"
                dataKey="download"
                stroke="#10b981"
                strokeWidth={1.8}
                fillOpacity={1}
                fill="url(#nocDlGrad)"
                name="Download"
                isAnimationActive={false}
                connectNulls={false}
              />
              <Area
                type="monotone"
                dataKey="upload"
                stroke="#00d4ff"
                strokeWidth={1.8}
                fillOpacity={1}
                fill="url(#nocUlGrad)"
                name="Upload"
                isAnimationActive={false}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {hoveredPoint && (
        <div className="noc-chart-readout">
          <span className="mono text-dim">{hoveredPoint.time}</span>
          <span className="noc-readout-sep">|</span>
          <span className="mono color-dl">↓ {hoveredPoint.download !== null ? `${hoveredPoint.download.toFixed(3)} Mbps` : 'NULL'}</span>
          <span className="noc-readout-sep">|</span>
          <span className="mono color-ul">↑ {hoveredPoint.upload !== null ? `${hoveredPoint.upload.toFixed(3)} Mbps` : 'NULL'}</span>
          <span className="noc-readout-sep">|</span>
          <span className="mono text-muted">{hoveredPoint.status}</span>
        </div>
      )}
    </div>
  );
};
