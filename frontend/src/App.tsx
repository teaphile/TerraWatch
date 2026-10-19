import React, { useCallback, useEffect, useState } from 'react';
import { Header, Sidebar, ErrorBoundary } from './components/Common';
import type { SidebarTab } from './components/Common';
import { MapView } from './components/Map';
import { SoilAnalysisPanel, RiskAnalysisPanel, RecommendationsPanel, ExportPanel } from './components/Analysis';
import { RiskSummary, AlertFeed, EarthquakeList } from './components/Dashboard';
import WeatherDashboard from './components/Dashboard/WeatherDashboard';
import api, { ApiError } from './services/api';
import wsService from './services/websocket';
import type { SoilAnalysis, RiskAssessment, EarthquakeEvent, Alert } from './types';

type Theme = 'dark' | 'light';

const App: React.FC = () => {
  // Theme
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('terrawatch-theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('light', theme === 'light');
    localStorage.setItem('terrawatch-theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  }, []);

  // UI state
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('soil');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Map state
  const [selectedPoint, setSelectedPoint] = useState<[number, number] | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Data state
  const [soilAnalysis, setSoilAnalysis] = useState<SoilAnalysis | null>(null);
  const [riskAssessment, setRiskAssessment] = useState<RiskAssessment | null>(null);
  const [earthquakes, setEarthquakes] = useState<EarthquakeEvent[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch earthquakes on mount and every 2 minutes
  useEffect(() => {
    const fetchQuakes = async () => {
      try {
        const res = await api.getEarthquakes(1, 2.5);
        // Backend returns { status, data: { count, events } }
        const data = res?.data ?? res;
        const events = data?.events ?? data?.earthquakes ?? (Array.isArray(data) ? data : []);
        setEarthquakes(events);
      } catch (err) {
        console.warn('Failed to fetch earthquakes:', err);
      }
    };

    fetchQuakes();
    const interval = setInterval(fetchQuakes, 120_000);
    return () => clearInterval(interval);
  }, []);

  // Fetch active alerts on mount
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await api.getActiveAlerts();
        // Backend returns { status, data: { count, alerts } }
        const data = res?.data ?? res;
        const list = data?.alerts ?? (Array.isArray(data) ? data : []);
        setAlerts(list);
      } catch (err) {
        console.warn('Failed to fetch alerts:', err);
      }
    };
    fetchAlerts();
  }, []);

  // WebSocket connection
  useEffect(() => {
    const unsub = wsService.onConnectionChange((connected) => {
      setWsConnected(connected);
    });

    wsService.connect();

    const unsubAlert = wsService.subscribe((alert) => {
      setAlerts((prev) => [alert, ...prev].slice(0, 100));
    });

    const unsubInitial = wsService.onInitial((snapshot) => {
      // Replace the snapshot returned by REST with the live one.
      setAlerts(snapshot.slice(0, 100));
    });

    return () => {
      unsub();
      unsubAlert();
      unsubInitial();
      wsService.disconnect();
    };
  }, []);

  // Handle map click — perform soil + risk analysis
  const handleMapClick = useCallback(async (lat: number, lon: number) => {
    setSelectedPoint([lat, lon]);
    setIsLoading(true);
    setSoilAnalysis(null);
    setRiskAssessment(null);
    setErrorMessage(null);

    try {
      const [soilRes, riskRes] = await Promise.allSettled([
        api.analyzeSoil(lat, lon),
        api.assessRisk(lat, lon),
      ]);

      if (soilRes.status === 'fulfilled') {
        const d = soilRes.value?.data ?? soilRes.value;
        setSoilAnalysis(d);
      }
      if (riskRes.status === 'fulfilled') {
        const d = riskRes.value?.data ?? riskRes.value;
        setRiskAssessment(d);
      }

      const failures = [soilRes, riskRes].filter(
        (result): result is PromiseRejectedResult => result.status === 'rejected',
      );
      if (failures.length === 2) {
        const reason = failures[0].reason;
        setErrorMessage(
          reason instanceof ApiError
            ? reason.message
            : 'Analysis failed. Please check that the backend is running.',
        );
      }

      if (soilRes.status === 'fulfilled' && sidebarCollapsed) {
        setSidebarCollapsed(false);
      }
    } catch (err) {
      console.error('Analysis failed:', err);
      setErrorMessage(err instanceof Error ? err.message : 'Analysis failed.');
    } finally {
      setIsLoading(false);
    }
  }, [sidebarCollapsed]);

  // Handle earthquake selection — fly to location
  const handleEarthquakeSelect = useCallback((eq: EarthquakeEvent) => {
    setSelectedPoint([eq.latitude, eq.longitude]);
  }, []);

  // Handle geolocation — browser Geolocation API
  const handleGeolocate = useCallback(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        handleMapClick(latitude, longitude);
      },
      (err) => console.warn('Geolocation error:', err.message),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, [handleMapClick]);

  // Handle coordinate search from header
  const handleCoordSearch = useCallback(
    (lat: number, lon: number) => {
      handleMapClick(lat, lon);
    },
    [handleMapClick],
  );

  // Dismiss alert (optimistic local update, synced to the backend)
  const handleDismissAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
    api.dismissAlert(id).catch((err) => {
      console.warn('Could not dismiss alert on the server:', err);
    });
  }, []);

  // Render sidebar panel content
  const renderSidebarContent = () => {
    switch (sidebarTab) {
      case 'soil':
        return <SoilAnalysisPanel analysis={soilAnalysis} />;
      case 'risk':
        return <RiskAnalysisPanel assessment={riskAssessment} />;
      case 'earthquakes':
        return <EarthquakeList earthquakes={earthquakes} onSelect={handleEarthquakeSelect} />;
      case 'alerts':
        return <AlertFeed alerts={alerts} onDismiss={handleDismissAlert} />;
      case 'recommendations':
        return (
          <RecommendationsPanel
            lat={selectedPoint?.[0] ?? null}
            lon={selectedPoint?.[1] ?? null}
          />
        );
      case 'export':
        return (
          <ExportPanel
            lat={selectedPoint?.[0] ?? null}
            lon={selectedPoint?.[1] ?? null}
          />
        );
      case 'weather':
        return (
          <WeatherDashboard
            soilAnalysis={soilAnalysis}
            riskAssessment={riskAssessment}
          />
        );
      default:
        return null;
    }
  };

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen bg-background text-text-primary overflow-hidden">
        <Header
          wsConnected={wsConnected}
          earthquakeCount={earthquakes.length}
          alertCount={alerts.length}
          theme={theme}
          onToggleTheme={toggleTheme}
          onGeolocate={handleGeolocate}
          onCoordSearch={handleCoordSearch}
          selectedPoint={selectedPoint}
        />

        <div className="flex flex-1 overflow-hidden pb-14 md:pb-0">
          <Sidebar
            activeTab={sidebarTab}
            onTabChange={setSidebarTab}
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
            alertCount={alerts.length}
          >
            {renderSidebarContent()}
          </Sidebar>

          <main className="flex-1 relative">
            <MapView
              earthquakes={earthquakes}
              soilAnalysis={soilAnalysis}
              riskAssessment={riskAssessment}
              selectedPoint={selectedPoint}
              onMapClick={handleMapClick}
              isLoading={isLoading}
              theme={theme}
            />

            {/* Quick Risk Summary — desktop bottom-right overlay, scrollable */}
            {riskAssessment && (
              <div className="hidden sm:block absolute top-20 right-3 z-[1000] w-72 max-h-[calc(100vh-160px)] overflow-y-auto glass-card p-3 shadow-xl scrollbar-thin">
                <RiskSummary assessment={riskAssessment} />
              </div>
            )}
          </main>
        </div>

        {errorMessage && (
          <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-[2000] max-w-[92vw] sm:max-w-md">
            <div className="glass-card border border-red-500/40 bg-red-500/10 px-4 py-3 shadow-xl flex items-start gap-3">
              <span className="text-red-400 text-sm font-semibold">!</span>
              <p className="text-xs text-text-primary flex-1">{errorMessage}</p>
              <button
                type="button"
                onClick={() => setErrorMessage(null)}
                className="text-text-muted hover:text-text-primary text-xs"
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
};

export default App;
