import { useState, useEffect, useRef, useCallback } from 'react';
import type { 
  SystemTelemetry, 
  NetworkThroughput, 
  ConnectionState, 
  WebSocketTelemetryMessage,
  ChartDataPoint,
  LatencySnapshot,
  HealthScoreData,
  AlertSummaryData,
  DeviceSummary,
  ConnectionSummary,
  ProtocolSummary
} from '../types/telemetry';

interface UseTelemetryReturn {
  systemData: SystemTelemetry | null;
  networkData: NetworkThroughput | null;
  latencyData: LatencySnapshot | null;
  healthScore: HealthScoreData | null;
  alertsSummary: AlertSummaryData | null;
  deviceSummary: DeviceSummary | null;
  connectionSummary: ConnectionSummary | null;
  protocolSummary: ProtocolSummary | null;
  connState: ConnectionState;
  lastMessageTime: number | null;
  lastSyncFormatted: string;
  liveChartPoints: ChartDataPoint[];
  reconnect: () => void;
  activeInterfaceName: string;
}

export function useTelemetry(maxLivePoints = 60): UseTelemetryReturn {
  const [systemData, setSystemData] = useState<SystemTelemetry | null>(null);
  const [networkData, setNetworkData] = useState<NetworkThroughput | null>(null);
  const [latencyData, setLatencyData] = useState<LatencySnapshot | null>(null);
  const [healthScore, setHealthScore] = useState<HealthScoreData | null>(null);
  const [alertsSummary, setAlertsSummary] = useState<AlertSummaryData | null>(null);
  const [deviceSummary, setDeviceSummary] = useState<DeviceSummary | null>(null);
  const [connectionSummary, setConnectionSummary] = useState<ConnectionSummary | null>(null);
  const [protocolSummary, setProtocolSummary] = useState<ProtocolSummary | null>(null);
  const [connState, setConnState] = useState<ConnectionState>('CONNECTING');
  const [lastMessageTime, setLastMessageTime] = useState<number | null>(null);
  const [lastSyncFormatted, setLastSyncFormatted] = useState<string>('—');
  const [liveChartPoints, setLiveChartPoints] = useState<ChartDataPoint[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const reconnectTimerRef = useRef<number | null>(null);
  
  // Strict bounded ring-buffer for sample_id deduplication (max 150 items)
  const seenIdsSet = useRef<Set<string>>(new Set());
  const seenIdsQueue = useRef<string[]>([]);
  const MAX_SAMPLE_ID_MEMORY = 150;

  const isDuplicateSample = useCallback((id: string): boolean => {
    if (!id) return false;
    if (seenIdsSet.current.has(id)) {
      return true;
    }
    seenIdsSet.current.add(id);
    seenIdsQueue.current.push(id);
    if (seenIdsQueue.current.length > MAX_SAMPLE_ID_MEMORY) {
      const oldest = seenIdsQueue.current.shift();
      if (oldest) seenIdsSet.current.delete(oldest);
    }
    return false;
  }, []);

  const fetchInitialSnapshot = useCallback(async () => {
    try {
      const [sysRes, netRes, latRes, healthRes, alertRes] = await Promise.all([
        fetch('/api/system/current'),
        fetch('/api/network/current'),
        fetch('/api/latency/current'),
        fetch('/api/health-score'),
        fetch('/api/alerts/summary')
      ]);
      if (sysRes.ok) {
        const sys: SystemTelemetry = await sysRes.json();
        setSystemData(sys);
      }
      if (netRes.ok) {
        const net: NetworkThroughput = await netRes.json();
        setNetworkData(net);
      }
      if (latRes.ok) {
        const lat: LatencySnapshot = await latRes.json();
        setLatencyData(lat);
      }
      if (healthRes.ok) {
        const health: HealthScoreData = await healthRes.json();
        setHealthScore(health);
      }
      if (alertRes.ok) {
        const alerts: AlertSummaryData = await alertRes.json();
        setAlertsSummary(alerts);
      }
    } catch (e) {
      console.warn('[useTelemetry] Initial REST bootstrap warning:', e);
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setConnState('CONNECTING');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onopen = () => {
      setConnState('LIVE');
      reconnectAttemptRef.current = 0;
    };

    socket.onmessage = (event) => {
      try {
        const payload: WebSocketTelemetryMessage = JSON.parse(event.data);
        const now = Date.now();

        if (payload.type === 'snapshot') {
          if (payload.sample_id) isDuplicateSample(payload.sample_id);
          setSystemData(payload.system);
          setNetworkData(payload.network);
          if (payload.latency) {
            setLatencyData(payload.latency);
          }
          if (payload.health_score) {
            setHealthScore(payload.health_score);
          }
          if (payload.alerts_summary) {
            setAlertsSummary(payload.alerts_summary);
          }
          setConnState('LIVE');
          setLastMessageTime(now);
          setLastSyncFormatted(new Date().toLocaleTimeString());
          return;
        }

        if (payload.type === 'telemetry') {
          if (payload.sample_id && isDuplicateSample(payload.sample_id)) {
            return;
          }

          setSystemData(payload.system);
          setNetworkData(payload.network);
          if (payload.latency) {
            setLatencyData(payload.latency);
          }
          if (payload.health_score) {
            setHealthScore(payload.health_score);
          }
          if (payload.alerts_summary) {
            setAlertsSummary(payload.alerts_summary);
          }
          if (payload.devices) {
            setDeviceSummary(payload.devices);
          }
          if (payload.connections) {
            setConnectionSummary(payload.connections);
          }
          if (payload.protocols) {
            setProtocolSummary(payload.protocols);
          }
          setConnState('LIVE');
          setLastMessageTime(now);
          setLastSyncFormatted(new Date().toLocaleTimeString());

          const d = new Date(payload.network.timestamp * 1000);
          const newPoint: ChartDataPoint = {
            time: d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            timestamp: payload.network.timestamp,
            download: payload.network.download_mbps,
            upload: payload.network.upload_mbps,
            status: payload.network.status
          };

          setLiveChartPoints(prev => [...prev, newPoint].slice(-maxLivePoints));
        }
      } catch (err) {
        console.error('[useTelemetry] Parsing error:', err);
      }
    };

    socket.onclose = () => {
      setConnState('OFFLINE');
      wsRef.current = null;

      const attempt = reconnectAttemptRef.current;
      const delay = Math.min(10000, 1000 * Math.pow(2, attempt));
      reconnectAttemptRef.current += 1;

      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = window.setTimeout(() => {
        connectWebSocket();
      }, delay);
    };

    socket.onerror = () => {
      socket.close();
    };
  }, [isDuplicateSample, maxLivePoints]);

  const reconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (wsRef.current) wsRef.current.close();
    connectWebSocket();
  }, [connectWebSocket]);

  useEffect(() => {
    const watchdog = setInterval(() => {
      if (connState === 'LIVE' && lastMessageTime) {
        const elapsedMs = Date.now() - lastMessageTime;
        if (elapsedMs > 9000) {
          setConnState('OFFLINE');
        } else if (elapsedMs > 4500) {
          setConnState('DELAYED');
        }
      }
    }, 1000);
    return () => clearInterval(watchdog);
  }, [connState, lastMessageTime]);

  useEffect(() => {
    fetchInitialSnapshot();
    connectWebSocket();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWebSocket, fetchInitialSnapshot]);

  const activeInterfaceName = networkData?.interfaces?.find(i => i.is_up && (i.download_mbps || i.bytes_recv > 0))?.name 
    || systemData?.interfaces?.find(i => i.is_up)?.name 
    || 'Wi-Fi';

  return {
    systemData,
    networkData,
    latencyData,
    healthScore,
    alertsSummary,
    deviceSummary,
    connectionSummary,
    protocolSummary,
    connState,
    lastMessageTime,
    lastSyncFormatted,
    liveChartPoints,
    reconnect,
    activeInterfaceName
  };
}
