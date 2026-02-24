import React from 'react';
import { Shield, Mountain, Droplets, Flame, Waves, ChevronDown, ChevronUp } from 'lucide-react';
import type { RiskAssessment } from '../../types';
import { RiskBarChart, RiskRadarChart, CompositeRiskGauge } from '../Dashboard/Charts';

interface RiskAnalysisPanelProps {
  assessment: RiskAssessment | null;
}

const RiskAnalysisPanel: React.FC<RiskAnalysisPanelProps> = ({ assessment }) => {
  const [expanded, setExpanded] = React.useState<string | null>(null);

  if (!assessment) {
    return (
      <div className="p-6 text-center text-text-muted">
        <Shield className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">Click on the map to assess disaster risk</p>
        <p className="text-xs mt-1">See landslide, flood, wildfire, and liquefaction risks</p>
      </div>
    );
  }

  const riskDetails = [
    {
      key: 'landslide',
      label: 'Landslide Risk',
      icon: Mountain,
      risk: assessment.risks.landslide,
      color: 'text-orange-400',
      details: [
        { label: 'Probability', value: `${(assessment.risks.landslide.probability * 100).toFixed(1)}%` },
        { label: 'Risk Level', value: assessment.risks.landslide.risk_level },
        ...(assessment.risks.landslide.contributing_factors || []).map((f, i) => ({
          label: `Factor ${i + 1}`,
          value: f,
        })),
      ],
    },
    {
      key: 'flood',
      label: 'Flood Risk',
      icon: Droplets,
      risk: assessment.risks.flood,
      color: 'text-blue-400',
      details: [
        { label: 'Probability', value: `${(assessment.risks.flood.probability * 100).toFixed(1)}%` },
        { label: 'Risk Level', value: assessment.risks.flood.risk_level },
        { label: 'Return Period', value: `${assessment.risks.flood.return_period_years} years` },
        { label: 'Max Inundation', value: `${assessment.risks.flood.max_inundation_depth_m.toFixed(1)} m` },
      ],
    },
    {
      key: 'wildfire',
      label: 'Wildfire Risk',
      icon: Flame,
      risk: assessment.risks.wildfire,
      color: 'text-red-400',
      details: [
        { label: 'Probability', value: `${(assessment.risks.wildfire.probability * 100).toFixed(1)}%` },
        { label: 'Risk Level', value: assessment.risks.wildfire.risk_level },
        { label: 'Vegetation Dryness', value: `${(assessment.risks.wildfire.vegetation_dryness_index * 100).toFixed(0)}%` },
      ],
    },
    {
      key: 'liquefaction',
      label: 'Liquefaction Risk',
      icon: Waves,
      risk: assessment.risks.liquefaction,
      color: 'text-purple-400',
      details: [
        { label: 'Susceptibility', value: assessment.risks.liquefaction.susceptibility },
        { label: 'Prob. (M7.0 event)', value: `${(assessment.risks.liquefaction.probability_given_m7 * 100).toFixed(1)}%` },
        { label: 'Soil Type Factor', value: assessment.risks.liquefaction.soil_type_factor },
      ],
    },
  ];

  return (
    <div className="space-y-4 overflow-y-auto max-h-[calc(100vh-140px)] pr-1 scrollbar-thin">
      {/* Composite Risk Gauge */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Composite Risk</p>
        <CompositeRiskGauge assessment={assessment} />
      </div>

      {/* Risk Radar */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Risk Profile</p>
        <RiskRadarChart assessment={assessment} />
      </div>

      {/* Bar Chart */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Risk Comparison</p>
        <RiskBarChart assessment={assessment} />
      </div>

      {/* Current Conditions */}
      {assessment.current_conditions && (
        <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
          <p className="text-xs font-medium text-text-secondary mb-2">Current Conditions</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-text-muted">Temperature</span>
              <p className="font-semibold">{assessment.current_conditions.temperature_c.toFixed(1)}°C</p>
            </div>
            <div>
              <span className="text-text-muted">Humidity</span>
              <p className="font-semibold">{assessment.current_conditions.humidity_pct.toFixed(0)}%</p>
            </div>
            <div>
              <span className="text-text-muted">Wind</span>
              <p className="font-semibold">{assessment.current_conditions.wind_speed_kmh.toFixed(1)} km/h</p>
            </div>
            <div>
              <span className="text-text-muted">Precipitation</span>
              <p className="font-semibold">{assessment.current_conditions.precipitation_mm.toFixed(1)} mm</p>
            </div>
            <div>
              <span className="text-text-muted">Soil Moisture</span>
              <p className="font-semibold">{assessment.current_conditions.soil_moisture_pct.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      )}

      {/* Individual Risks */}
      {riskDetails.map(({ key, label, icon: Icon, color, details }) => (
        <div
          key={key}
          className="bg-surface-700/30 rounded-lg border border-surface-600 overflow-hidden"
        >
          <button
            className="w-full flex items-center justify-between p-3 hover:bg-surface-700/50 transition-colors"
            onClick={() => setExpanded(expanded === key ? null : key)}
          >
            <div className="flex items-center gap-2">
              <Icon className={`w-4 h-4 ${color}`} />
              <span className="text-sm font-medium text-text-primary">{label}</span>
            </div>
            {expanded === key ? (
              <ChevronUp className="w-4 h-4 text-text-muted" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-muted" />
            )}
          </button>
          {expanded === key && (
            <div className="px-3 pb-3 space-y-1.5">
              {details.map(({ label: l, value }) => (
                <div key={l} className="flex justify-between text-xs">
                  <span className="text-text-muted">{l}</span>
                  <span className="text-text-primary font-medium">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Timestamp */}
      <p className="text-[10px] text-text-muted text-center">
        Assessed at {new Date(assessment.timestamp).toLocaleString()}
      </p>
    </div>
  );
};

export default RiskAnalysisPanel;
