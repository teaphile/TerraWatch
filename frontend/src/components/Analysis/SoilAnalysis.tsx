import React from 'react';
import { Leaf, Droplets, Thermometer, Scale } from 'lucide-react';
import type { SoilAnalysis } from '../../types';
import { SoilRadarChart, TextureDonutChart, MoistureDepthChart, ErosionFactorsChart, CarbonGaugeChart, SoilNutrientChart, HealthBreakdownChart, SoilCompositionChart } from '../Dashboard/Charts';

interface SoilAnalysisPanelProps {
  analysis: SoilAnalysis | null;
}

function getHealthColor(grade: string): string {
  switch (grade) {
    case 'A':
      return 'text-green-400';
    case 'B+':
      return 'text-green-500';
    case 'B':
      return 'text-yellow-400';
    case 'C':
      return 'text-orange-500';
    default:
      return 'text-red-500';
  }
}

function getHealthBg(grade: string): string {
  switch (grade) {
    case 'A':
      return 'bg-green-500/10 border-green-500/30';
    case 'B+':
      return 'bg-green-500/10 border-green-500/30';
    case 'B':
      return 'bg-yellow-500/10 border-yellow-500/30';
    case 'C':
      return 'bg-orange-500/10 border-orange-500/30';
    default:
      return 'bg-red-500/10 border-red-500/30';
  }
}

const SoilAnalysisPanel: React.FC<SoilAnalysisPanelProps> = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="p-6 text-center text-text-muted">
        <Leaf className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">Click on the map to analyze soil health</p>
        <p className="text-xs mt-1">Get detailed soil properties, erosion risk, and carbon data</p>
      </div>
    );
  }

  const sp = analysis.soil_properties;

  return (
    <div className="space-y-4 overflow-y-auto max-h-[calc(100vh-140px)] pr-1 scrollbar-thin">
      {/* Health Score */}
      <div className={`p-4 rounded-lg border ${getHealthBg(analysis.health_index.grade)}`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-text-secondary">Soil Health Index</p>
            <p className={`text-2xl font-bold ${getHealthColor(analysis.health_index.grade)}`}>
              {analysis.health_index.score.toFixed(0)}/100
            </p>
          </div>
          <div className="text-right">
            <span
              className={`text-3xl font-bold ${getHealthColor(analysis.health_index.grade)}`}
            >
              {analysis.health_index.grade}
            </span>
            <p className="text-xs text-text-muted mt-1">{analysis.health_index.category}</p>
          </div>
        </div>
      </div>

      {/* Radar Chart */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Property Overview</p>
        <SoilRadarChart analysis={analysis} />
      </div>

      {/* Properties Grid */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Soil Properties</p>
        <div className="grid grid-cols-2 gap-3">
          <PropertyCard
            icon={<Thermometer className="w-3.5 h-3.5 text-blue-400" />}
            label="pH"
            value={sp.ph.value.toFixed(1)}
            sub={sp.ph.category || ''}
          />
          <PropertyCard
            icon={<Leaf className="w-3.5 h-3.5 text-green-400" />}
            label="Organic Carbon"
            value={`${sp.organic_carbon_pct.value.toFixed(2)}%`}
            sub=""
          />
          <PropertyCard
            icon={<Scale className="w-3.5 h-3.5 text-yellow-400" />}
            label="Nitrogen"
            value={`${sp.nitrogen_pct.value.toFixed(3)}%`}
            sub=""
          />
          <PropertyCard
            icon={<Droplets className="w-3.5 h-3.5 text-cyan-400" />}
            label="Moisture"
            value={`${sp.moisture_pct.value.toFixed(1)}%`}
            sub=""
          />
          <PropertyCard
            icon={<Scale className="w-3.5 h-3.5 text-orange-400" />}
            label="Bulk Density"
            value={`${sp.bulk_density_gcm3.toFixed(2)} g/cm³`}
            sub=""
          />
          <PropertyCard
            icon={<Scale className="w-3.5 h-3.5 text-purple-400" />}
            label="CEC"
            value={`${sp.cec_cmolkg.toFixed(1)} cmol/kg`}
            sub=""
          />
        </div>
      </div>

      {/* Texture */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-1">
          Soil Texture: <span className="text-text-primary">{sp.texture.classification}</span>
        </p>
        <TextureDonutChart analysis={analysis} />
      </div>

      {/* Erosion Risk */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Erosion Risk (RUSLE)</p>
        <div className="flex items-center justify-between mb-2">
          <span className="text-lg font-bold text-text-primary">
            {analysis.erosion_risk.rusle_value_tons_ha_yr.toFixed(1)} t/ha/yr
          </span>
          <span
            className={`text-sm font-medium px-2 py-0.5 rounded ${
              analysis.erosion_risk.risk_level === 'Severe' || analysis.erosion_risk.risk_level === 'High'
                ? 'bg-red-500/10 text-red-400'
                : analysis.erosion_risk.risk_level === 'Moderate'
                ? 'bg-yellow-500/10 text-yellow-400'
                : 'bg-green-500/10 text-green-400'
            }`}
          >
            {analysis.erosion_risk.risk_level}
          </span>
        </div>
        <ErosionFactorsChart analysis={analysis} />
      </div>

      {/* Carbon Sequestration */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Carbon Sequestration</p>
        <CarbonGaugeChart analysis={analysis} />
        <div className="space-y-2 mt-2">
          <div className="flex justify-between text-sm">
            <span className="text-text-muted">Current Stock</span>
            <span className="text-text-primary">
              {analysis.carbon_sequestration.current_stock_tons_ha.toFixed(1)} t/ha
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-text-muted">Potential</span>
            <span className="text-green-400">
              {analysis.carbon_sequestration.potential_stock_tons_ha.toFixed(1)} t/ha
            </span>
          </div>
          <p className="text-xs text-text-muted text-right">
            +{analysis.carbon_sequestration.improvement_potential_pct.toFixed(0)}% improvement possible
          </p>
        </div>
      </div>

      {/* Nutrient Analysis */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Nutrient Analysis</p>
        <SoilNutrientChart analysis={analysis} />
      </div>

      {/* Health Breakdown */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Health Component Breakdown</p>
        <HealthBreakdownChart analysis={analysis} />
      </div>

      {/* Soil Composition */}
      <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
        <p className="text-xs font-medium text-text-secondary mb-2">Soil Composition</p>
        <SoilCompositionChart analysis={analysis} />
      </div>

      {/* Soil Moisture */}
      {analysis.soil_moisture && (
        <div className="bg-surface-700/30 rounded-lg p-3 border border-surface-600">
          <p className="text-xs font-medium text-text-secondary mb-2">Soil Moisture Profile</p>
          <MoistureDepthChart analysis={analysis} />
          <div className="space-y-1.5">
            {[
              { label: 'Surface (0-1cm)', value: analysis.soil_moisture.surface_0_1cm },
              { label: 'Shallow (1-3cm)', value: analysis.soil_moisture.shallow_1_3cm },
              { label: 'Mid (3-9cm)', value: analysis.soil_moisture.mid_3_9cm },
              { label: 'Deep (9-27cm)', value: analysis.soil_moisture.deep_9_27cm },
            ].map(({ label, value }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-xs text-text-muted w-28">{label}</span>
                <div className="flex-1 bg-surface-600 rounded-full h-1.5">
                  <div
                    className="bg-cyan-400 h-1.5 rounded-full"
                    style={{ width: `${Math.min(100, (value ?? 0) * 100 / 0.5)}%` }}
                  />
                </div>
                <span className="text-xs text-text-primary w-14 text-right">
                  {value != null ? `${(value * 100).toFixed(0)}%` : 'N/A'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

function PropertyCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="bg-surface-700/50 rounded p-2">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[10px] text-text-muted">{label}</span>
      </div>
      <p className="text-sm font-bold text-text-primary">{value}</p>
      {sub && <p className="text-[10px] text-text-secondary">{sub}</p>}
    </div>
  );
}

export default SoilAnalysisPanel;
