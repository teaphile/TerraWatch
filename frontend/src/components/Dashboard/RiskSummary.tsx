import React from 'react';
import {
  AlertTriangle,
  Droplets,
  Mountain,
  Flame,
  Waves,
  Shield,
} from 'lucide-react';
import type { RiskAssessment } from '../../types';
import { RiskBarChart, RiskComparisonChart } from './Charts';

interface RiskSummaryProps {
  assessment: RiskAssessment | null;
}

function getRiskColor(level: string): string {
  switch (level?.toLowerCase()) {
    case 'critical':
    case 'severe':
    case 'very high':
      return 'text-red-500';
    case 'high':
      return 'text-orange-500';
    case 'moderate':
    case 'medium':
      return 'text-yellow-500';
    case 'low':
      return 'text-green-500';
    default:
      return 'text-blue-400';
  }
}

function getRiskBg(level: string): string {
  switch (level?.toLowerCase()) {
    case 'critical':
    case 'severe':
    case 'very high':
      return 'bg-red-500/10 border-red-500/30';
    case 'high':
      return 'bg-orange-500/10 border-orange-500/30';
    case 'moderate':
    case 'medium':
      return 'bg-yellow-500/10 border-yellow-500/30';
    case 'low':
      return 'bg-green-500/10 border-green-500/30';
    default:
      return 'bg-blue-500/10 border-blue-500/30';
  }
}

const RiskSummary: React.FC<RiskSummaryProps> = ({ assessment }) => {
  if (!assessment) {
    return (
      <div className="p-4 text-center text-text-muted">
        <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />
        <p className="text-sm">Click on the map to assess disaster risk</p>
      </div>
    );
  }

  const risks = [
    {
      key: 'landslide',
      label: 'Landslide',
      icon: Mountain,
      level: assessment.risks.landslide.risk_level,
      value: (assessment.risks.landslide.probability * 100).toFixed(0),
    },
    {
      key: 'flood',
      label: 'Flood',
      icon: Droplets,
      level: assessment.risks.flood.risk_level,
      value: (assessment.risks.flood.probability * 100).toFixed(0),
    },
    {
      key: 'wildfire',
      label: 'Wildfire',
      icon: Flame,
      level: assessment.risks.wildfire.risk_level,
      value: (assessment.risks.wildfire.probability * 100).toFixed(0),
    },
    {
      key: 'liquefaction',
      label: 'Liquefaction',
      icon: Waves,
      level: assessment.risks.liquefaction.susceptibility,
      value: (assessment.risks.liquefaction.probability_given_m7 * 100).toFixed(0),
    },
  ];

  return (
    <div className="space-y-3">
      {/* Composite Score */}
      <div
        className={`p-3 rounded-lg border ${getRiskBg(assessment.composite_risk_level)}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className={`w-5 h-5 ${getRiskColor(assessment.composite_risk_level)}`} />
            <span className="text-sm font-medium text-text-primary">Composite Risk</span>
          </div>
          <span className={`text-lg font-bold ${getRiskColor(assessment.composite_risk_level)}`}>
            {assessment.composite_risk_score}%
          </span>
        </div>
        <p className={`text-xs mt-1 ${getRiskColor(assessment.composite_risk_level)}`}>
          {assessment.composite_risk_level}
        </p>
      </div>

      {/* Individual Risks */}
      <div className="grid grid-cols-2 gap-2">
        {risks.map(({ key, label, icon: Icon, level, value }) => (
          <div
            key={key}
            className="bg-surface-700/50 rounded-lg p-2.5 border border-surface-600"
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className={`w-3.5 h-3.5 ${getRiskColor(level)}`} />
              <span className="text-xs text-text-secondary">{label}</span>
            </div>
            <p className={`text-lg font-bold ${getRiskColor(level)}`}>{value}%</p>
            <p className={`text-xs ${getRiskColor(level)}`}>{level}</p>
          </div>
        ))}
      </div>

      {/* Current Conditions */}
      {assessment.current_conditions && (
        <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
          <p className="text-xs text-text-primary font-medium mb-2">Current Conditions</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-text-secondary">Temperature</span>
            <span className="text-text-primary font-medium">
              {assessment.current_conditions.temperature_c?.toFixed(1) ?? 'N/A'}°C
            </span>
            <span className="text-text-secondary">Humidity</span>
            <span className="text-text-primary font-medium">
              {assessment.current_conditions.humidity_pct?.toFixed(0) ?? 'N/A'}%
            </span>
            <span className="text-text-secondary">Wind</span>
            <span className="text-text-primary font-medium">
              {assessment.current_conditions.wind_speed_kmh?.toFixed(0) ?? 'N/A'} km/h
            </span>
            <span className="text-text-secondary">Precipitation</span>
            <span className="text-text-primary font-medium">
              {assessment.current_conditions.precipitation_mm?.toFixed(1) ?? 'N/A'} mm
            </span>
          </div>
        </div>
      )}

      {/* Risk Charts */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-semibold text-text-primary mb-2">Risk Distribution</p>
        <RiskBarChart assessment={assessment} />
      </div>

      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-semibold text-text-primary mb-2">Risk Trend</p>
        <RiskComparisonChart assessment={assessment} />
      </div>
    </div>
  );
};

export default RiskSummary;
