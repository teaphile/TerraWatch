/**
 * DataQualityBanner — Shows data source attribution and quality warnings.
 *
 * Displays when API responses contain estimated/fallback data so users
 * can clearly distinguish real data from heuristic estimates.
 */
import React, { useState } from 'react';
import { AlertTriangle, Info, ChevronDown, ChevronUp, CheckCircle } from 'lucide-react';

interface DataQuality {
  sources?: string[];
  warnings?: string[];
  soil_data_source?: string;
  weather_data_source?: string;
  weather_source?: string;
  soil_moisture_source?: string;
  is_fully_real_data?: boolean;
  note?: string;
}

interface Props {
  dataQuality?: DataQuality | null;
  compact?: boolean;
}

const DataQualityBanner: React.FC<Props> = ({ dataQuality, compact = false }) => {
  const [expanded, setExpanded] = useState(false);

  if (!dataQuality) return null;

  const warnings = dataQuality.warnings || [];
  const sources = dataQuality.sources || [];
  const isReal = dataQuality.is_fully_real_data;

  if (isReal && warnings.length === 0) {
    // All data is real — show a small green badge
    if (compact) return null;
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-green-900/30 text-green-400 text-xs">
        <CheckCircle size={12} />
        <span>All data from live APIs</span>
      </div>
    );
  }

  // There are warnings or estimated data
  const severity = warnings.length >= 3 ? 'high' : warnings.length >= 1 ? 'medium' : 'low';
  const bgColor = severity === 'high' ? 'bg-red-900/30' : severity === 'medium' ? 'bg-yellow-900/30' : 'bg-blue-900/30';
  const textColor = severity === 'high' ? 'text-red-400' : severity === 'medium' ? 'text-yellow-400' : 'text-blue-400';
  const borderColor = severity === 'high' ? 'border-red-800' : severity === 'medium' ? 'border-yellow-800' : 'border-blue-800';

  if (compact) {
    return (
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded ${bgColor} ${textColor} text-xs`}>
        <AlertTriangle size={12} />
        <span>
          {warnings.length > 0
            ? `${warnings.length} data quality warning${warnings.length > 1 ? 's' : ''}`
            : 'Some data estimated'}
        </span>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border ${borderColor} ${bgColor} p-3 text-xs ${textColor}`}>
      <button
        className="flex items-center justify-between w-full text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} />
          <span className="font-medium">
            Data Quality: {isReal ? 'Good' : 'Contains Estimates'}
          </span>
        </div>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {warnings.length > 0 && (
            <div>
              <p className="font-medium mb-1">Warnings:</p>
              <ul className="list-disc list-inside space-y-0.5 opacity-90">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {sources.length > 0 && (
            <div>
              <p className="font-medium mb-1">Data Sources:</p>
              <div className="flex flex-wrap gap-1">
                {sources.map((s, i) => (
                  <span
                    key={i}
                    className="px-1.5 py-0.5 rounded bg-black/20 text-[10px] uppercase tracking-wider"
                  >
                    {s.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {dataQuality.note && (
            <div className="flex items-start gap-1.5 opacity-80">
              <Info size={12} className="mt-0.5 shrink-0" />
              <span>{dataQuality.note}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DataQualityBanner;
