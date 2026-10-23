import React, { useState } from 'react';
import { useTelemetry } from './hooks/useTelemetry';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { InterfacesPage } from './pages/InterfacesPage';
import { HistoryPage } from './pages/HistoryPage';
import { NetworkPage } from './pages/NetworkPage';
import { AlertsPage } from './pages/AlertsPage';
import { DevicesPage } from './pages/DevicesPage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { ProtocolsPage } from './pages/ProtocolsPage';
import type { ActivePage } from './types/telemetry';

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<ActivePage>('overview');
  const {
    systemData,
    networkData,
    latencyData,
    healthScore,
    alertsSummary,
    deviceSummary,
    connectionSummary,
    protocolSummary,
    connState,
    lastSyncFormatted,
    liveChartPoints,
    reconnect,
    activeInterfaceName
  } = useTelemetry(60);

  const isOffline = connState === 'OFFLINE';

  return (
    <div className="noc-app-shell">
      {/* 1. Top Status Header */}
      <Header
        connState={connState}
        activeInterface={activeInterfaceName}
        lastSyncFormatted={lastSyncFormatted}
        onReconnect={reconnect}
      />

      {/* 2. Main Body: Sidebar Navigation + Dynamic Page View */}
      <div className="noc-body-layout">
        <Sidebar
          activePage={activePage}
          onSelectPage={setActivePage}
          interfaceCount={systemData?.interfaces?.length ?? 0}
          activeAlertCount={alertsSummary?.total_active ?? 0}
          onlineDeviceCount={deviceSummary?.online ?? 0}
          connectionCount={connectionSummary?.total ?? 0}
          protocolStatus={protocolSummary?.status ?? 'PERMISSION_REQUIRED'}
        />

        <main className="noc-main-content">
          {activePage === 'overview' && (
            <OverviewPage
              system={systemData}
              network={networkData}
              latency={latencyData}
              health={healthScore}
              liveChartPoints={liveChartPoints}
              isOffline={isOffline}
            />
          )}

          {activePage === 'network' && (
            <NetworkPage
              liveChartPoints={liveChartPoints}
              totals={systemData?.network_totals}
              latency={latencyData}
              isOffline={isOffline}
            />
          )}

          {activePage === 'interfaces' && (
            <InterfacesPage
              system={systemData}
              network={networkData}
            />
          )}

          {activePage === 'history' && (
            <HistoryPage />
          )}

          {activePage === 'alerts' && (
            <AlertsPage
              alertsSummary={alertsSummary}
            />
          )}

          {activePage === 'devices' && (
            <DevicesPage
              deviceSummary={deviceSummary}
            />
          )}

          {activePage === 'connections' && (
            <ConnectionsPage
              connectionSummary={connectionSummary}
            />
          )}

          {activePage === 'protocols' && (
            <ProtocolsPage
              protocolSummary={protocolSummary}
            />
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
