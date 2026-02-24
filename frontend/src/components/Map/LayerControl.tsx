import React from 'react';
import { Layers, Eye, EyeOff } from 'lucide-react';

interface LayerControlProps {
  layers: Record<string, boolean>;
  onToggle: (layerId: string) => void;
}

const LAYER_LABELS: Record<string, { label: string; color: string }> = {
  earthquakes: { label: 'Earthquakes', color: '#f59e0b' },
  soilHealth: { label: 'Soil Health', color: '#22c55e' },
  riskZones: { label: 'Risk Zones', color: '#dc2626' },
  terrain: { label: 'Terrain', color: '#8B5CF6' },
};

const LayerControl: React.FC<LayerControlProps> = ({ layers, onToggle }) => {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="bg-surface-800 border border-surface-600 rounded-lg shadow-lg">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 text-text-primary hover:bg-surface-700 rounded-lg transition-colors w-full"
      >
        <Layers className="w-4 h-4" />
        <span className="text-sm font-medium">Layers</span>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-1">
          {Object.entries(layers).map(([id, visible]) => {
            const meta = LAYER_LABELS[id] || { label: id, color: '#888' };
            return (
              <button
                key={id}
                onClick={() => onToggle(id)}
                className="flex items-center gap-2 w-full px-2 py-1.5 rounded hover:bg-surface-700 transition-colors"
              >
                {visible ? (
                  <Eye className="w-3.5 h-3.5 text-text-secondary" />
                ) : (
                  <EyeOff className="w-3.5 h-3.5 text-text-muted" />
                )}
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: meta.color, opacity: visible ? 1 : 0.3 }}
                />
                <span
                  className={`text-xs ${visible ? 'text-text-primary' : 'text-text-muted'}`}
                >
                  {meta.label}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default LayerControl;
