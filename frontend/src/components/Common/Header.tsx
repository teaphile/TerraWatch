import React, { useState, useCallback, useEffect } from 'react';
import {
  Globe,
  Wifi,
  WifiOff,
  Activity,
  Sun,
  Moon,
  Search,
  MapPin,
  Crosshair,
  X,
} from 'lucide-react';

interface HeaderProps {
  wsConnected: boolean;
  earthquakeCount: number;
  alertCount: number;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  onGeolocate?: () => void;
  onCoordSearch?: (lat: number, lon: number) => void;
  selectedPoint?: [number, number] | null;
}

const Header: React.FC<HeaderProps> = ({
  wsConnected,
  earthquakeCount,
  alertCount,
  theme,
  onToggleTheme,
  onGeolocate,
  onCoordSearch,
  selectedPoint,
}) => {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const handleSearch = useCallback(() => {
    if (!onCoordSearch) return;
    const parts = searchInput.split(/[,\s]+/).filter(Boolean);
    if (parts.length >= 2) {
      const lat = parseFloat(parts[0]);
      const lon = parseFloat(parts[1]);
      if (!isNaN(lat) && !isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
        onCoordSearch(lat, lon);
        setSearchOpen(false);
        setSearchInput('');
      }
    }
  }, [searchInput, onCoordSearch]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleSearch();
      if (e.key === 'Escape') {
        setSearchOpen(false);
        setSearchInput('');
      }
    },
    [handleSearch]
  );

  return (
    <header className="h-12 bg-surface-800 border-b border-surface-600 flex items-center justify-between px-2 sm:px-4 flex-shrink-0 safe-top no-print relative">
      {/* Logo */}
      <div className="flex items-center gap-2 min-w-0">
        <Globe className="w-5 h-5 sm:w-6 sm:h-6 text-primary-400 flex-shrink-0" />
        <div className="min-w-0">
          <h1 className="text-xs sm:text-sm font-bold text-text-primary leading-none truncate">
            TerraWatch
          </h1>
          <p className="text-[8px] sm:text-[9px] text-text-muted leading-none mt-0.5 hidden sm:block">
            Soil &amp; Disaster Monitoring
          </p>
        </div>
      </div>

      {/* Center: Coordinate Search (desktop) */}
      <div className="hidden md:flex items-center gap-2 flex-1 justify-center max-w-md">
        {searchOpen ? (
          <div className="flex items-center gap-1.5 bg-surface-700 border border-surface-600 rounded-lg px-3 py-1.5 w-72">
            <Search className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Lat, Lon (e.g. 28.6139, 77.2090)"
              className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none flex-1 font-mono"
              autoFocus
            />
            <button
              onClick={() => { setSearchOpen(false); setSearchInput(''); }}
              className="text-text-muted hover:text-text-secondary"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSearchOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-700/50 border border-surface-600 hover:bg-surface-700 transition-colors text-text-secondary hover:text-text-primary"
            >
              <Search className="w-3.5 h-3.5" />
              <span className="text-xs">Search coordinates…</span>
            </button>
            {onGeolocate && (
              <button
                onClick={onGeolocate}
                className="p-1.5 rounded-lg hover:bg-surface-600 transition-colors text-text-secondary hover:text-text-primary"
                title="Use my location"
              >
                <Crosshair className="w-4 h-4" />
              </button>
            )}
            {selectedPoint && (
              <span className="coord-chip">
                <MapPin className="w-3 h-3" />
                {selectedPoint[0].toFixed(4)}, {selectedPoint[1].toFixed(4)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div className="flex items-center gap-1.5 sm:gap-3">
        {/* Mobile Search & Geolocate */}
        <button
          onClick={() => setSearchOpen((o) => !o)}
          className="md:hidden p-1.5 rounded-md hover:bg-surface-600 transition-colors text-text-secondary"
        >
          <Search className="w-4 h-4" />
        </button>
        {onGeolocate && (
          <button
            onClick={onGeolocate}
            className="md:hidden p-1.5 rounded-md hover:bg-surface-600 transition-colors text-text-secondary"
            title="Use my location"
          >
            <Crosshair className="w-4 h-4" />
          </button>
        )}

        {/* Earthquake Count */}
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-text-secondary">
          <Activity className="w-3.5 h-3.5 text-yellow-500" />
          <span>{earthquakeCount}</span>
          <span className="hidden lg:inline">quakes</span>
        </div>

        {/* Alert Count */}
        {alertCount > 0 && (
          <div className="flex items-center gap-1">
            <span className="relative flex h-2 w-2 sm:h-2.5 sm:w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-full w-full bg-red-500" />
            </span>
            <span className="text-[10px] sm:text-xs text-red-400 font-medium">
              {alertCount}<span className="hidden sm:inline"> alerts</span>
            </span>
          </div>
        )}

        {/* UTC Clock */}
        <span className="hidden xl:block text-[10px] text-text-muted font-mono">
          {now.toISOString().slice(11, 16)} UTC
        </span>

        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          className="p-1.5 rounded-md hover:bg-surface-600 transition-colors text-text-secondary hover:text-text-primary"
          title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* WebSocket Status */}
        <div className="flex items-center gap-1">
          {wsConnected ? (
            <Wifi className="w-3.5 h-3.5 text-green-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-red-400" />
          )}
          <span className={`text-[10px] hidden sm:inline ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
            {wsConnected ? 'Live' : 'Offline'}
          </span>
        </div>
      </div>

      {/* Mobile Search Overlay */}
      {searchOpen && (
        <div className="md:hidden absolute top-12 left-0 right-0 z-[2000] bg-surface-800 border-b border-surface-600 p-3 fade-in">
          <div className="flex items-center gap-2 bg-surface-700 border border-surface-600 rounded-lg px-3 py-2">
            <Search className="w-4 h-4 text-text-muted flex-shrink-0" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Lat, Lon (e.g. 28.6139, 77.2090)"
              className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none flex-1 font-mono"
              autoFocus
              inputMode="decimal"
            />
            <button
              onClick={handleSearch}
              className="px-3 py-1 bg-primary-600 text-white rounded-md text-xs font-medium"
            >
              Go
            </button>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
