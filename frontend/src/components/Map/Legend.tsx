import React from 'react';

const MapLegend: React.FC = () => {
  const [collapsed, setCollapsed] = React.useState(false);

  const quakeLevels = [
    { label: 'M7+', color: '#dc2626' },
    { label: 'M6', color: '#ea580c' },
    { label: 'M5', color: '#f59e0b' },
    { label: 'M4', color: '#eab308' },
    { label: 'M3', color: '#84cc16' },
    { label: '<M3', color: '#6b7280' },
  ];

  const riskLevels = [
    { label: 'Critical', color: '#dc2626' },
    { label: 'High', color: '#ea580c' },
    { label: 'Moderate', color: '#f59e0b' },
    { label: 'Low', color: '#22c55e' },
    { label: 'Minimal', color: '#3b82f6' },
  ];

  const soilHealthLevels = [
    { label: 'Good (70+)', color: '#22c55e' },
    { label: 'Fair (50-70)', color: '#f59e0b' },
    { label: 'Poor (<50)', color: '#dc2626' },
  ];

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="bg-surface-800 border border-surface-600 rounded-lg px-3 py-2 text-xs text-text-secondary hover:bg-surface-700 transition-colors"
      >
        Legend
      </button>
    );
  }

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg p-3 text-xs min-w-[140px] shadow-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-text-primary">Legend</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-text-muted hover:text-text-secondary transition-colors"
          aria-label="Collapse legend"
        >
          ×
        </button>
      </div>

      <div className="mb-2">
        <p className="text-text-primary mb-1 font-medium">Earthquakes</p>
        <div className="space-y-0.5">
          {quakeLevels.map((l) => (
            <div key={l.label} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: l.color }}
              />
              <span className="text-text-secondary">{l.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="text-text-primary mb-1 font-medium">Risk Level</p>
        <div className="space-y-0.5">
          {riskLevels.map((l) => (
            <div key={l.label} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: l.color }}
              />
              <span className="text-text-secondary">{l.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="text-text-primary mb-1 font-medium">Soil Health</p>
        <div className="space-y-0.5">
          {soilHealthLevels.map((l) => (
            <div key={l.label} className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: l.color }}
              />
              <span className="text-text-secondary">{l.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MapLegend;
