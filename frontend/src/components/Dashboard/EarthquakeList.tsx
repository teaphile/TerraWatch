import React, { useMemo, useState } from 'react';
import { Activity, BarChart3, List, TrendingUp } from 'lucide-react';
import type { EarthquakeEvent } from '../../types';
import { EarthquakeMagDistChart, EarthquakeDepthMagChart, EarthquakeTimelineChart } from './Charts';

interface EarthquakeListProps {
  earthquakes: EarthquakeEvent[];
  onSelect?: (eq: EarthquakeEvent) => void;
}

function getMagColor(mag: number): string {
  if (mag >= 7) return 'text-red-500 bg-red-500/10';
  if (mag >= 6) return 'text-orange-500 bg-orange-500/10';
  if (mag >= 5) return 'text-yellow-500 bg-yellow-500/10';
  if (mag >= 4) return 'text-yellow-400 bg-yellow-400/10';
  return 'text-green-400 bg-green-400/10';
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const EarthquakeList: React.FC<EarthquakeListProps> = ({ earthquakes, onSelect }) => {
  const [view, setView] = useState<'list' | 'charts'>('list');

  const sorted = useMemo(
    () =>
      [...earthquakes].sort(
        (a, b) => new Date(b.event_time).getTime() - new Date(a.event_time).getTime(),
      ),
    [earthquakes],
  );

  const stats = useMemo(() => {
    if (earthquakes.length === 0) return null;
    const mags = earthquakes.map((e) => e.magnitude);
    const depths = earthquakes.map((e) => e.depth_km);
    return {
      count: earthquakes.length,
      maxMag: Math.max(...mags),
      avgMag: mags.reduce((s, v) => s + v, 0) / mags.length,
      avgDepth: depths.reduce((s, v) => s + v, 0) / depths.length,
      tsunamiCount: earthquakes.filter((e) => e.tsunami).length,
      felt: earthquakes.filter((e) => e.felt && e.felt > 0).length,
    };
  }, [earthquakes]);

  if (earthquakes.length === 0) {
    return (
      <div className="p-4 text-center text-text-muted">
        <Activity className="w-6 h-6 mx-auto mb-2 opacity-30" />
        <p className="text-sm">No recent earthquakes</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-3 gap-2">
          <div className="glass-card p-2 text-center">
            <p className="text-lg font-bold text-text-primary">{stats.count}</p>
            <p className="text-[10px] text-text-muted">Events</p>
          </div>
          <div className="glass-card p-2 text-center">
            <p className={`text-lg font-bold ${stats.maxMag >= 5 ? 'text-red-400' : 'text-yellow-400'}`}>
              M{stats.maxMag.toFixed(1)}
            </p>
            <p className="text-[10px] text-text-muted">Strongest</p>
          </div>
          <div className="glass-card p-2 text-center">
            <p className="text-lg font-bold text-text-primary">{stats.avgDepth.toFixed(0)}</p>
            <p className="text-[10px] text-text-muted">Avg Depth km</p>
          </div>
        </div>
      )}

      {/* View toggle */}
      <div className="flex gap-1">
        <button
          onClick={() => setView('list')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded text-xs transition-colors ${
            view === 'list'
              ? 'bg-primary-600 text-white'
              : 'bg-surface-700/50 text-text-secondary hover:text-text-primary'
          }`}
        >
          <List className="w-3.5 h-3.5" /> List
        </button>
        <button
          onClick={() => setView('charts')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded text-xs transition-colors ${
            view === 'charts'
              ? 'bg-primary-600 text-white'
              : 'bg-surface-700/50 text-text-secondary hover:text-text-primary'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" /> Charts
        </button>
      </div>

      {view === 'charts' ? (
        <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-260px)] pr-1 scrollbar-thin">
          <div className="glass-card p-3">
            <p className="text-xs font-medium text-text-secondary mb-2">Magnitude Distribution</p>
            <EarthquakeMagDistChart earthquakes={earthquakes} />
          </div>
          <div className="glass-card p-3">
            <p className="text-xs font-medium text-text-secondary mb-2">Depth vs Magnitude</p>
            <EarthquakeDepthMagChart earthquakes={earthquakes} />
          </div>
          <div className="glass-card p-3">
            <p className="text-xs font-medium text-text-secondary mb-2">Timeline (24h)</p>
            <EarthquakeTimelineChart earthquakes={earthquakes} />
          </div>
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[calc(100vh-260px)] overflow-y-auto pr-1 scrollbar-thin">
          {sorted.slice(0, 50).map((eq) => (
            <button
              key={eq.event_id}
              onClick={() => onSelect?.(eq)}
              className="w-full text-left p-2.5 rounded-lg bg-surface-700/30 border border-surface-600 hover:bg-surface-700/60 transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={`text-sm font-bold w-12 text-center py-1 rounded ${getMagColor(eq.magnitude)}`}
                >
                  {eq.magnitude.toFixed(1)}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text-primary truncate">{eq.place}</p>
                  <div className="flex items-center gap-2 text-[10px] text-text-muted mt-0.5">
                    <span>{eq.depth_km.toFixed(0)} km deep</span>
                    <span>·</span>
                    <span>{timeAgo(eq.event_time)}</span>
                    {eq.tsunami && <span className="text-red-400">🌊 Tsunami</span>}
                    {eq.felt != null && eq.felt > 0 && <span>👥 {eq.felt}</span>}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default EarthquakeList;
