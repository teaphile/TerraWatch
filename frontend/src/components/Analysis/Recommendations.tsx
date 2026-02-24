import React, { useEffect, useState } from 'react';
import { Sprout, ShieldCheck, TreePine, Loader2 } from 'lucide-react';
import api from '../../services/api';
import type { AgricultureRecommendations } from '../../types';

interface RecommendationsPanelProps {
  lat: number | null;
  lon: number | null;
}

type Tab = 'agriculture' | 'disaster' | 'restoration';

const RecommendationsPanel: React.FC<RecommendationsPanelProps> = ({ lat, lon }) => {
  const [tab, setTab] = useState<Tab>('agriculture');
  const [agData, setAgData] = useState<AgricultureRecommendations | null>(null);
  const [disasterData, setDisasterData] = useState<any>(null);
  const [restorationData, setRestorationData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (lat == null || lon == null) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        if (tab === 'agriculture') {
          const res = await api.getAgricultureRecs(lat, lon);
          setAgData(res?.data ?? res);
        } else if (tab === 'disaster') {
          const res = await api.getDisasterPrep(lat, lon);
          setDisasterData(res?.data ?? res);
        } else {
          const res = await api.getRestorationRecs(lat, lon);
          setRestorationData(res?.data ?? res);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load recommendations');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [lat, lon, tab]);

  if (lat == null || lon == null) {
    return (
      <div className="p-6 text-center text-text-muted">
        <Sprout className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">Select a location to get recommendations</p>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: typeof Sprout }[] = [
    { key: 'agriculture', label: 'Agriculture', icon: Sprout },
    { key: 'disaster', label: 'Preparedness', icon: ShieldCheck },
    { key: 'restoration', label: 'Restoration', icon: TreePine },
  ];

  return (
    <div className="space-y-3">
      {/* Tabs */}
      <div className="flex gap-1 bg-surface-700/50 rounded-lg p-1">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
              tab === key
                ? 'bg-primary-600 text-white'
                : 'text-text-secondary hover:text-text-primary hover:bg-surface-600'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center p-8">
          <Loader2 className="w-6 h-6 animate-spin text-primary-400" />
        </div>
      ) : error ? (
        <div className="p-4 text-center text-red-400 text-sm">{error}</div>
      ) : (
        <div className="overflow-y-auto max-h-[calc(100vh-140px)] pr-1 scrollbar-thin">
          {tab === 'agriculture' && agData && <AgricultureView data={agData} />}
          {tab === 'disaster' && disasterData && <GenericRecsView data={disasterData} />}
          {tab === 'restoration' && restorationData && <GenericRecsView data={restorationData} />}
        </div>
      )}
    </div>
  );
};

function AgricultureView({ data }: { data: AgricultureRecommendations }) {
  return (
    <div className="space-y-3">
      {/* Summary */}
      {data.summary && (
        <div className="bg-primary-600/10 border border-primary-600/30 rounded-lg p-3">
          <p className="text-xs text-text-secondary">{data.summary}</p>
        </div>
      )}

      {/* Suitable Crops */}
      {data.suitable_crops && data.suitable_crops.length > 0 && (
        <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
          <p className="text-xs font-medium text-text-secondary mb-2">Suitable Crops</p>
          <div className="space-y-1.5">
            {data.suitable_crops.map((crop, i) => {
              // score is 4-8; normalize to 0-100%
              const pct = Math.min(100, Math.round((crop.suitability_score / 8) * 100));
              return (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-text-primary">{crop.crop}</span>
                    {crop.suitability && (
                      <span className="ml-1.5 text-[10px] text-text-muted">({crop.suitability})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-16 bg-surface-600 rounded-full h-1.5">
                      <div
                        className="bg-green-500 h-1.5 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-text-muted w-12 text-right">{pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Fertilizer */}
      {data.fertilizer_recommendations && data.fertilizer_recommendations.length > 0 && (
        <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
          <p className="text-xs font-medium text-text-secondary mb-2">Fertilizer Recommendations</p>
          <div className="space-y-2">
            {data.fertilizer_recommendations.map((rec, i) => (
              <div key={i} className="text-xs">
                <p className="text-text-primary font-medium">{rec.nutrient}: {rec.status}</p>
                <p className="text-text-muted">{rec.recommendation}</p>
                <p className="text-green-400/80">🌿 {rec.organic_alternative}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Irrigation */}
      {data.irrigation_schedule && (
        <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
          <p className="text-xs font-medium text-text-secondary mb-2">Irrigation Schedule</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-text-muted">Frequency</span>
            <span className="text-text-primary">{data.irrigation_schedule.irrigation_frequency}</span>
            <span className="text-text-muted">Depth</span>
            <span className="text-text-primary">{data.irrigation_schedule.irrigation_depth}</span>
            <span className="text-text-muted">Method</span>
            <span className="text-text-primary">{data.irrigation_schedule.method}</span>
            <span className="text-text-muted">Best Time</span>
            <span className="text-text-primary">{data.irrigation_schedule.best_time}</span>
            <span className="text-text-muted">Urgency</span>
            <span className="text-text-primary">{data.irrigation_schedule.urgency}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function GenericRecsView({ data }: { data: any }) {
  if (!data) return null;

  // Unwrap {status, data} wrapper if present
  const inner = data?.data ?? data;
  const items = Array.isArray(inner)
    ? inner
    : inner.recommendations || inner.items || inner.preparedness_actions || [];

  if (Array.isArray(items) && items.length > 0) {
    return (
      <div className="space-y-2">
        {/* Summary */}
        {inner.summary && (
          <div className="bg-primary-600/10 border border-primary-600/30 rounded-lg p-3">
            <p className="text-xs text-text-secondary">{inner.summary}</p>
          </div>
        )}
        {items.map((item: any, i: number) => (
          <div key={i} className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
            {item.category && (
              <p className="text-xs font-medium text-primary-400 mb-1">{item.category}</p>
            )}
            {item.title && (
              <p className="text-sm text-text-primary font-medium">{item.title}</p>
            )}
            {item.priority && (
              <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded mt-0.5 ${
                item.priority === 'high' ? 'bg-red-500/10 text-red-400' :
                item.priority === 'medium' ? 'bg-yellow-500/10 text-yellow-400' :
                'bg-green-500/10 text-green-400'
              }`}>{item.priority}</span>
            )}
            <p className="text-xs text-text-secondary mt-0.5">
              {item.description || item.recommendation || item.action || ''}
            </p>
            {item.actions && Array.isArray(item.actions) && (
              <ul className="mt-1.5 space-y-0.5">
                {item.actions.map((a: string, j: number) => (
                  <li key={j} className="text-xs text-text-muted flex items-start gap-1">
                    <span className="text-primary-400">•</span> {a}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    );
  }

  // Fallback: render key-value pairs nicely
  if (typeof inner === 'object' && inner !== null) {
    return (
      <div className="space-y-2">
        {Object.entries(inner).map(([key, val]) => (
          <div key={key} className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
            <p className="text-xs font-medium text-primary-400 mb-1">
              {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </p>
            <p className="text-xs text-text-secondary">
              {typeof val === 'string' ? val : JSON.stringify(val, null, 2)}
            </p>
          </div>
        ))}
      </div>
    );
  }

  return null;
}

export default RecommendationsPanel;
