import React, { useState, useEffect } from 'react';
import { apiUrl } from '../utils/api';
import type { ChartDataPoint, NetworkTotals, LatencySnapshot } from '../types/telemetry';
import { ThroughputChart } from '../components/charts/ThroughputChart';
import type { TimeRangeOption } from '../components/charts/ThroughputChart';
import { NetworkTotalsGrid } from '../components/metrics/NetworkTotalsGrid';
import { NetworkQualitySection } from '../components/metrics/NetworkQualitySection';

interface NetworkPageProps {
  liveChartPoints: ChartDataPoint[];
  totals?: NetworkTotals;
  latency?: LatencySnapshot | null;
  isOffline?: boolean;
}

export const NetworkPage: React.FC<NetworkPageProps> = ({ 
  liveChartPoints, 
  totals,
  latency = null,
  isOffline = false
}) => {
  const [selectedRange, setSelectedRange] = useState<TimeRangeOption>('LIVE');
  const [historicalPoints, setHistoricalPoints] = useState<ChartDataPoint[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  useEffect(() => {
    if (selectedRange === 'LIVE') {
      setHistoricalPoints([]);
      return;
    }

    let limit = 60;
    if (selectedRange === '5m') limit = 150;
    else if (selectedRange === '15m') limit = 450;
    else if (selectedRange === '1h') limit = 1000;

    setIsLoadingHistory(true);
    fetch(apiUrl(`/api/network/history?limit=${limit}&order=asc`))
      .then(res => res.json())
      .then(data => {
        const points: ChartDataPoint[] = (data.items || []).map((item: any) => {
          const d = new Date(item.timestamp * 1000);
          return {
            time: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            timestamp: item.timestamp,
            download: item.download_mbps,
            upload: item.upload_mbps,
            status: item.status
          };
        });
        setHistoricalPoints(points);
      })
      .catch(err => {
        console.error('Failed to load historical range:', err);
      })
      .finally(() => {
        setIsLoadingHistory(false);
      });
  }, [selectedRange]);

  const activeChartData = selectedRange === 'LIVE' ? liveChartPoints : historicalPoints;

  return (
    <div className="noc-page-container">
      <NetworkQualitySection
        latency={latency}
        isOffline={isOffline}
      />

      <ThroughputChart
        data={activeChartData}
        selectedRange={selectedRange}
        onRangeChange={setSelectedRange}
        isLoading={isLoadingHistory}
      />

      <div style={{ marginTop: '20px' }}>
        <NetworkTotalsGrid totals={totals} />
      </div>
    </div>
  );
};
