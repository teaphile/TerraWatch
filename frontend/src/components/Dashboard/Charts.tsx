// Recharts-based data visualizations for soil, risk, earthquake, and weather data.

import React from 'react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  Legend,
  LineChart,
  Line,
  ComposedChart,
  Scatter,
  ScatterChart,
  ZAxis,
  ReferenceLine,
} from 'recharts';
import type { SoilAnalysis, RiskAssessment, EarthquakeEvent, WeatherData } from '../../types';



const CHART_COLORS = {
  primary: '#2D6A4F',
  secondary: '#40916C',
  accent: '#52B788',
  warning: '#F59E0B',
  danger: '#DC2626',
  info: '#3B82F6',
  cyan: '#06B6D4',
  purple: '#8B5CF6',
  pink: '#EC4899',
  orange: '#F97316',
  teal: '#14B8A6',
  lime: '#84CC16',
};

const TEXTURE_COLORS = ['#D4A373', '#52B788', '#2D6A4F'];

const tooltipStyle: React.CSSProperties = {
  backgroundColor: 'var(--surface-card)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  color: 'var(--text-primary)',
  fontSize: '12px',
  fontWeight: 500,
  padding: '8px 12px',
  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
};

const axisStyle = { fill: 'var(--text-secondary)', fontSize: 11, fontWeight: 500 };
const gridStroke = 'var(--border-color)';



interface SoilRadarProps { analysis: SoilAnalysis; }
interface RiskBarProps { assessment: RiskAssessment; }
interface TextureDonutProps { analysis: SoilAnalysis; }

export const SoilRadarChart: React.FC<SoilRadarProps> = ({ analysis }) => {
  const sp = analysis.soil_properties;
  const data = [
    { property: 'pH',        value: Math.min(100, (sp.ph.value / 14) * 100) },
    { property: 'Org. C',    value: Math.min(100, sp.organic_carbon_pct.value * 20) },
    { property: 'Nitrogen',  value: Math.min(100, sp.nitrogen_pct.value * 200) },
    { property: 'Moisture',  value: Math.min(100, sp.moisture_pct.value) },
    { property: 'CEC',       value: Math.min(100, (sp.cec_cmolkg / 50) * 100) },
    { property: 'Health',    value: analysis.health_index.score },
    { property: 'Density',   value: Math.min(100, (sp.bulk_density_gcm3 / 2.0) * 100) },
  ];

  return (
    <div className="w-full h-[200px] sm:h-[220px]">
      <ResponsiveContainer>
        <RadarChart data={data}>
          <PolarGrid stroke={gridStroke} />
          <PolarAngleAxis dataKey="property" tick={{ ...axisStyle, fontSize: 9 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 8 }} />
          <Radar name="Soil" dataKey="value" stroke={CHART_COLORS.primary} fill={CHART_COLORS.accent} fillOpacity={0.3} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const RiskBarChart: React.FC<RiskBarProps> = ({ assessment }) => {
  const data = [
    { name: 'Landslide', risk: +(assessment.risks.landslide.probability * 100).toFixed(0) },
    { name: 'Flood',     risk: +(assessment.risks.flood.probability * 100).toFixed(0) },
    { name: 'Wildfire',  risk: +(assessment.risks.wildfire.probability * 100).toFixed(0) },
    { name: 'Liquefac.', risk: +(assessment.risks.liquefaction.probability_given_m7 * 100).toFixed(0) },
  ];

  const getColor = (v: number) => v >= 70 ? CHART_COLORS.danger : v >= 40 ? CHART_COLORS.warning : CHART_COLORS.accent;

  return (
    <div className="w-full h-[180px] sm:h-[200px]">
      <ResponsiveContainer>
        <BarChart data={data} barSize={24}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="name" tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <YAxis domain={[0, 100]} tick={axisStyle} axisLine={{ stroke: gridStroke }} unit="%" />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v}%`, 'Risk']} />
          <Bar dataKey="risk" radius={[4, 4, 0, 0]}>
            {data.map((e, i) => <Cell key={i} fill={getColor(e.risk)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const RiskRadarChart: React.FC<RiskBarProps> = ({ assessment }) => {
  const r = assessment.risks;
  const data = [
    { risk: 'Landslide',    value: +(r.landslide.probability * 100).toFixed(0) },
    { risk: 'Flood',        value: +(r.flood.probability * 100).toFixed(0) },
    { risk: 'Wildfire',     value: +(r.wildfire.probability * 100).toFixed(0) },
    { risk: 'Liquefaction', value: +(r.liquefaction.probability_given_m7 * 100).toFixed(0) },
  ];

  return (
    <div className="w-full h-[200px]">
      <ResponsiveContainer>
        <RadarChart data={data}>
          <PolarGrid stroke={gridStroke} />
          <PolarAngleAxis dataKey="risk" tick={{ ...axisStyle, fontSize: 9 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 8 }} />
          <Radar name="Risk" dataKey="value" stroke={CHART_COLORS.danger} fill={CHART_COLORS.danger} fillOpacity={0.2} strokeWidth={2} dot={{ r: 4, fill: CHART_COLORS.danger }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const TextureDonutChart: React.FC<TextureDonutProps> = ({ analysis }) => {
  const data = [
    { name: 'Sand', value: analysis.soil_properties.texture.sand_pct },
    { name: 'Silt', value: analysis.soil_properties.texture.silt_pct },
    { name: 'Clay', value: analysis.soil_properties.texture.clay_pct },
  ];

  return (
    <div className="w-full h-[160px] sm:h-[180px]">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={35} outerRadius={60} paddingAngle={3} dataKey="value"
            label={({ name, value }) => `${name}: ${value.toFixed(0)}%`}>
            {data.map((_, i) => <Cell key={i} fill={TEXTURE_COLORS[i]} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)}%`]} />
          <Legend wrapperStyle={{ fontSize: 10, color: 'var(--text-secondary)' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};



export const MoistureDepthChart: React.FC<{ analysis: SoilAnalysis }> = ({ analysis }) => {
  const m = analysis.soil_moisture;
  if (!m) return null;

  const data = [
    { depth: '0-1cm',  moisture: +((m.surface_0_1cm ?? 0) * 100).toFixed(1) },
    { depth: '1-3cm',  moisture: +((m.shallow_1_3cm ?? 0) * 100).toFixed(1) },
    { depth: '3-9cm',  moisture: +((m.mid_3_9cm ?? 0) * 100).toFixed(1) },
    { depth: '9-27cm', moisture: +((m.deep_9_27cm ?? 0) * 100).toFixed(1) },
  ];

  return (
    <div className="w-full h-[180px] sm:h-[200px]">
      <ResponsiveContainer>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="depth" tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <YAxis domain={[0, 'auto']} tick={axisStyle} axisLine={{ stroke: gridStroke }} unit="%" />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v}%`, 'Moisture']} />
          <defs>
            <linearGradient id="moistureGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={CHART_COLORS.cyan} stopOpacity={0.5} />
              <stop offset="95%" stopColor={CHART_COLORS.cyan} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="moisture" stroke={CHART_COLORS.cyan} fill="url(#moistureGrad)" strokeWidth={2} dot={{ r: 3, fill: CHART_COLORS.cyan }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};



export const ErosionFactorsChart: React.FC<{ analysis: SoilAnalysis }> = ({ analysis }) => {
  const factors = analysis.erosion_risk.factors;
  if (!factors) return null;

  const factorLabels: Record<string, string> = { R: 'Rainfall', K: 'Erodibility', LS: 'Slope', C: 'Cover', P: 'Practice' };
  const data = Object.entries(factors).map(([key, val]) => ({
    factor: factorLabels[key.toUpperCase()] || key.toUpperCase(),
    value: +(val as number).toFixed(3),
  }));

  const barColors = [CHART_COLORS.info, CHART_COLORS.warning, CHART_COLORS.accent, CHART_COLORS.purple, CHART_COLORS.teal];

  return (
    <div className="w-full h-[160px] sm:h-[180px]">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" barSize={14}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis type="number" tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <YAxis type="category" dataKey="factor" tick={axisStyle} axisLine={{ stroke: gridStroke }} width={55} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => <Cell key={i} fill={barColors[i % barColors.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const CarbonGaugeChart: React.FC<{ analysis: SoilAnalysis }> = ({ analysis }) => {
  const current = analysis.carbon_sequestration.current_stock_tons_ha;
  const potential = analysis.carbon_sequestration.potential_stock_tons_ha;
  const pct = Math.min(100, Math.round((current / potential) * 100));

  const data = [
    { name: 'Current', value: pct },
    { name: 'Remaining', value: 100 - pct },
  ];

  return (
    <div className="w-full h-[140px] sm:h-[160px] relative">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} cx="50%" cy="75%" startAngle={180} endAngle={0} innerRadius={45} outerRadius={65} dataKey="value" stroke="none">
            <Cell fill={CHART_COLORS.accent} />
            <Cell fill="var(--border-color)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-3">
        <span className="text-lg sm:text-xl font-bold text-text-primary">{pct}%</span>
        <span className="text-[9px] sm:text-[10px] text-text-muted">of carbon potential</span>
      </div>
    </div>
  );
};



export const RiskComparisonChart: React.FC<RiskBarProps> = ({ assessment }) => {
  const r = assessment.risks;
  const data = [
    { category: 'Landslide',    probability: +(r.landslide.probability * 100).toFixed(0) },
    { category: 'Flood',        probability: +(r.flood.probability * 100).toFixed(0) },
    { category: 'Wildfire',     probability: +(r.wildfire.probability * 100).toFixed(0) },
    { category: 'Liquefaction', probability: +(r.liquefaction.probability_given_m7 * 100).toFixed(0) },
  ];

  return (
    <div className="w-full h-[180px] sm:h-[200px]">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="category" tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <YAxis domain={[0, 100]} tick={axisStyle} axisLine={{ stroke: gridStroke }} unit="%" />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v}%`, 'Probability']} />
          <ReferenceLine y={50} stroke={CHART_COLORS.warning} strokeDasharray="5 5" label={{ value: 'Moderate', fill: 'var(--text-muted)', fontSize: 9 }} />
          <Line type="monotone" dataKey="probability" stroke={CHART_COLORS.danger} strokeWidth={2} dot={{ fill: CHART_COLORS.danger, r: 5 }} activeDot={{ r: 7 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

// Nutrient comparison

export const SoilNutrientChart: React.FC<{ analysis: SoilAnalysis }> = ({ analysis }) => {
  const sp = analysis.soil_properties;
  // Normalize to comparable 0-100 scale
  const data = [
    { nutrient: 'pH',      value: +sp.ph.value.toFixed(1),                  optimal: 6.5,   unit: '' },
    { nutrient: 'Org. C%', value: +sp.organic_carbon_pct.value.toFixed(2),  optimal: 3.0,   unit: '%' },
    { nutrient: 'N%',      value: +(sp.nitrogen_pct.value * 100).toFixed(1), optimal: 0.3 * 100, unit: '×10⁻²%' },
    { nutrient: 'CEC',     value: +sp.cec_cmolkg.toFixed(1),                optimal: 25,    unit: 'cmol/kg' },
  ];

  return (
    <div className="w-full h-[180px]">
      <ResponsiveContainer>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="nutrient" tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <YAxis tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="value" name="Measured" fill={CHART_COLORS.info} radius={[4, 4, 0, 0]} barSize={20} />
          <Line type="monotone" dataKey="optimal" name="Optimal" stroke={CHART_COLORS.accent} strokeWidth={2} strokeDasharray="5 5" dot={{ r: 3, fill: CHART_COLORS.accent }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};



export const HealthBreakdownChart: React.FC<{ analysis: SoilAnalysis }> = ({ analysis }) => {
  const sp = analysis.soil_properties;
  // Health score components (genuine calculation from soil properties)
  const phScore = Math.max(0, 100 - Math.abs(sp.ph.value - 6.5) * 20);
  const organicScore = Math.min(100, sp.organic_carbon_pct.value * 25);
  const moistureScore = Math.min(100, sp.moisture_pct.value * 2.5);
  const cecScore = Math.min(100, (sp.cec_cmolkg / 40) * 100);

  const data = [
    { name: 'pH Balance',    value: +phScore.toFixed(0), color: CHART_COLORS.info },
    { name: 'Organic Matter', value: +organicScore.toFixed(0), color: CHART_COLORS.accent },
    { name: 'Moisture',       value: +moistureScore.toFixed(0), color: CHART_COLORS.cyan },
    { name: 'CEC',            value: +cecScore.toFixed(0), color: CHART_COLORS.purple },
  ];

  return (
    <div className="w-full h-[180px]">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" outerRadius={65} innerRadius={30} dataKey="value" paddingAngle={2}
            label={({ name, value }) => `${name}: ${value}`}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};



export const EarthquakeMagDistChart: React.FC<{ earthquakes: EarthquakeEvent[] }> = ({ earthquakes }) => {
  if (earthquakes.length === 0) return null;

  // Bin earthquakes by magnitude
  const bins: Record<string, number> = { '2-3': 0, '3-4': 0, '4-5': 0, '5-6': 0, '6-7': 0, '7+': 0 };
  earthquakes.forEach((eq) => {
    const m = eq.magnitude;
    if (m >= 7)      bins['7+']++;
    else if (m >= 6) bins['6-7']++;
    else if (m >= 5) bins['5-6']++;
    else if (m >= 4) bins['4-5']++;
    else if (m >= 3) bins['3-4']++;
    else             bins['2-3']++;
  });

  const data = Object.entries(bins).map(([range, count]) => ({ range, count }));
  const barColors = [CHART_COLORS.lime, CHART_COLORS.accent, CHART_COLORS.warning, CHART_COLORS.orange, CHART_COLORS.danger, '#991B1B'];

  return (
    <div className="w-full h-[180px]">
      <ResponsiveContainer>
        <BarChart data={data} barSize={20}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="range" tick={axisStyle} axisLine={{ stroke: gridStroke }} label={{ value: 'Magnitude', position: 'insideBottom', offset: -2, fill: 'var(--text-muted)', fontSize: 9 }} />
          <YAxis tick={axisStyle} axisLine={{ stroke: gridStroke }} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v, 'Events']} />
          <Bar dataKey="count" name="Events" radius={[4, 4, 0, 0]}>
            {data.map((_, i) => <Cell key={i} fill={barColors[i]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const EarthquakeDepthMagChart: React.FC<{ earthquakes: EarthquakeEvent[] }> = ({ earthquakes }) => {
  if (earthquakes.length === 0) return null;

  const data = earthquakes.slice(0, 50).map((eq) => ({
    depth: +eq.depth_km.toFixed(1),
    magnitude: +eq.magnitude.toFixed(1),
    place: eq.place,
  }));

  return (
    <div className="w-full h-[200px]">
      <ResponsiveContainer>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="depth" name="Depth" tick={axisStyle} axisLine={{ stroke: gridStroke }} unit=" km"
            label={{ value: 'Depth (km)', position: 'insideBottom', offset: -2, fill: 'var(--text-muted)', fontSize: 9 }} />
          <YAxis dataKey="magnitude" name="Magnitude" tick={axisStyle} axisLine={{ stroke: gridStroke }}
            label={{ value: 'Mag', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 9 }} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number, name: string) => [v, name]} />
          <Scatter data={data} fill={CHART_COLORS.warning}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.magnitude >= 6 ? CHART_COLORS.danger : d.magnitude >= 4.5 ? CHART_COLORS.warning : CHART_COLORS.accent} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};



export const EarthquakeTimelineChart: React.FC<{ earthquakes: EarthquakeEvent[] }> = ({ earthquakes }) => {
  if (earthquakes.length === 0) return null;

  // Group by hour for the last 24 hours
  const now = Date.now();
  const hourBuckets: { hour: string; count: number; maxMag: number }[] = [];
  for (let h = 23; h >= 0; h--) {
    const start = now - (h + 1) * 3600_000;
    const end = now - h * 3600_000;
    const inBucket = earthquakes.filter((eq) => {
      const t = new Date(eq.event_time).getTime();
      return t >= start && t < end;
    });
    hourBuckets.push({
      hour: `${24 - h - 1}h`,
      count: inBucket.length,
      maxMag: inBucket.length > 0 ? Math.max(...inBucket.map((e) => e.magnitude)) : 0,
    });
  }

  return (
    <div className="w-full h-[180px]">
      <ResponsiveContainer>
        <ComposedChart data={hourBuckets}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="hour" tick={axisStyle} axisLine={{ stroke: gridStroke }} interval={3} />
          <YAxis yAxisId="count" tick={axisStyle} axisLine={{ stroke: gridStroke }} allowDecimals={false} />
          <YAxis yAxisId="mag" orientation="right" domain={[0, 10]} tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar yAxisId="count" dataKey="count" name="Events" fill={CHART_COLORS.info} radius={[2, 2, 0, 0]} barSize={8} />
          <Line yAxisId="mag" type="monotone" dataKey="maxMag" name="Max Mag" stroke={CHART_COLORS.danger} strokeWidth={1.5} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};



export const WeatherConditionsChart: React.FC<{ weather: WeatherData }> = ({ weather }) => {
  const data = [
    { metric: 'Temp',      value: +weather.temperature_c.toFixed(1),  unit: '°C',    color: CHART_COLORS.danger },
    { metric: 'Humidity',   value: +weather.humidity_pct.toFixed(0),   unit: '%',     color: CHART_COLORS.cyan },
    { metric: 'Wind',       value: +weather.wind_speed_kmh.toFixed(0), unit: 'km/h',  color: CHART_COLORS.info },
    { metric: 'Rain',       value: +weather.rain_mm.toFixed(1),        unit: 'mm',    color: CHART_COLORS.purple },
  ];

  return (
    <div className="w-full h-[180px]">
      <ResponsiveContainer>
        <BarChart data={data} barSize={28}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="metric" tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <YAxis tick={axisStyle} axisLine={{ stroke: gridStroke }} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number, _: any, entry: any) => [`${v} ${entry.payload.unit}`, entry.payload.metric]} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const CompositeRiskGauge: React.FC<{ assessment: RiskAssessment }> = ({ assessment }) => {
  const score = assessment.composite_risk_score;
  const gaugeData = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score },
  ];

  const color = score >= 70 ? CHART_COLORS.danger : score >= 40 ? CHART_COLORS.warning : CHART_COLORS.accent;

  return (
    <div className="w-full h-[120px] relative">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={gaugeData} cx="50%" cy="80%" startAngle={180} endAngle={0} innerRadius={40} outerRadius={55} dataKey="value" stroke="none">
            <Cell fill={color} />
            <Cell fill="var(--border-color)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
        <span className="text-2xl font-bold" style={{ color }}>{score}%</span>
        <span className="text-[9px] text-text-muted">{assessment.composite_risk_level}</span>
      </div>
    </div>
  );
};



export const SoilCompositionChart: React.FC<{ analysis: SoilAnalysis }> = ({ analysis }) => {
  const t = analysis.soil_properties.texture;
  const data = [{ name: 'Texture', sand: t.sand_pct, silt: t.silt_pct, clay: t.clay_pct }];

  return (
    <div className="w-full h-[60px]">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" barSize={24}>
          <XAxis type="number" domain={[0, 100]} tick={axisStyle} axisLine={{ stroke: gridStroke }} unit="%" />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)}%`]} />
          <Bar dataKey="sand" name="Sand" stackId="a" fill={TEXTURE_COLORS[0]} />
          <Bar dataKey="silt" name="Silt" stackId="a" fill={TEXTURE_COLORS[1]} />
          <Bar dataKey="clay" name="Clay" stackId="a" fill={TEXTURE_COLORS[2]} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};



export const EnvironmentalRadarChart: React.FC<{ assessment: RiskAssessment }> = ({ assessment }) => {
  const c = assessment.current_conditions;
  if (!c) return null;

  const data = [
    { metric: 'Temp',       value: Math.min(100, Math.max(0, ((c.temperature_c + 10) / 50) * 100)) },
    { metric: 'Humidity',   value: c.humidity_pct },
    { metric: 'Wind',       value: Math.min(100, (c.wind_speed_kmh / 100) * 100) },
    { metric: 'Precip',     value: Math.min(100, (c.precipitation_mm / 50) * 100) },
    { metric: 'Soil Moist', value: c.soil_moisture_pct },
  ];

  return (
    <div className="w-full h-[200px]">
      <ResponsiveContainer>
        <RadarChart data={data}>
          <PolarGrid stroke={gridStroke} />
          <PolarAngleAxis dataKey="metric" tick={{ ...axisStyle, fontSize: 9 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 8 }} />
          <Radar name="Conditions" dataKey="value" stroke={CHART_COLORS.info} fill={CHART_COLORS.info} fillOpacity={0.2} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};
