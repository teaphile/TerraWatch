import React from 'react';
import {
  Thermometer,
  Droplets,
  Wind,
  CloudRain,
  Compass,
  Sun,
  CloudSun,
  Cloud,
  CloudSnow,
  CloudLightning,
  CloudFog,
  Gauge,
} from 'lucide-react';
import { WeatherConditionsChart, EnvironmentalRadarChart } from './Charts';
import type { SoilAnalysis, RiskAssessment } from '../../types';

interface WeatherDashboardProps {
  soilAnalysis: SoilAnalysis | null;
  riskAssessment: RiskAssessment | null;
}

/** Map WMO weather codes to icon + label */
function weatherCodeInfo(code: number): { icon: React.ReactNode; label: string } {
  if (code === 0) return { icon: <Sun className="w-5 h-5 text-yellow-400" />, label: 'Clear sky' };
  if (code <= 3) return { icon: <CloudSun className="w-5 h-5 text-gray-300" />, label: 'Partly cloudy' };
  if (code <= 49) return { icon: <CloudFog className="w-5 h-5 text-gray-400" />, label: 'Fog / Haze' };
  if (code <= 69) return { icon: <CloudRain className="w-5 h-5 text-blue-400" />, label: 'Rain' };
  if (code <= 79) return { icon: <CloudSnow className="w-5 h-5 text-blue-200" />, label: 'Snow' };
  if (code <= 99) return { icon: <CloudLightning className="w-5 h-5 text-yellow-300" />, label: 'Thunderstorm' };
  return { icon: <Cloud className="w-5 h-5 text-gray-400" />, label: 'Unknown' };
}

function windDirection(deg: number): string {
  const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return dirs[Math.round(deg / 22.5) % 16];
}

const WeatherDashboard: React.FC<WeatherDashboardProps> = ({ soilAnalysis, riskAssessment }) => {
  const w = soilAnalysis?.climate?.current_weather;
  const c = riskAssessment?.current_conditions;

  if (!w && !c) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-text-muted">
        <CloudSun className="w-12 h-12 mb-3 opacity-40" />
        <p className="text-sm">Click a point on the map to view weather data</p>
      </div>
    );
  }

  const temp = w?.temperature_c ?? c?.temperature_c ?? 0;
  const humidity = w?.humidity_pct ?? c?.humidity_pct ?? 0;
  const windSpd = w?.wind_speed_kmh ?? c?.wind_speed_kmh ?? 0;
  const windDir = w?.wind_direction_deg ?? 0;
  const precip = w?.precipitation_mm ?? c?.precipitation_mm ?? 0;
  const rain = w?.rain_mm ?? 0;
  const code = w?.weather_code ?? 0;
  const soilMoisture = c?.soil_moisture_pct ?? 0;

  const { icon: wxIcon, label: wxLabel } = weatherCodeInfo(code);

  const metrics = [
    { label: 'Temperature', value: `${temp.toFixed(1)}°C`, icon: <Thermometer className="w-4 h-4" />, color: temp > 35 ? 'text-red-400' : temp < 0 ? 'text-blue-400' : 'text-green-400' },
    { label: 'Humidity', value: `${humidity.toFixed(0)}%`, icon: <Droplets className="w-4 h-4" />, color: humidity > 80 ? 'text-blue-400' : 'text-text-secondary' },
    { label: 'Wind', value: `${windSpd.toFixed(1)} km/h`, icon: <Wind className="w-4 h-4" />, color: windSpd > 50 ? 'text-red-400' : 'text-text-secondary' },
    { label: 'Direction', value: `${windDirection(windDir)} (${windDir.toFixed(0)}°)`, icon: <Compass className="w-4 h-4" />, color: 'text-text-secondary' },
    { label: 'Precipitation', value: `${precip.toFixed(1)} mm`, icon: <CloudRain className="w-4 h-4" />, color: precip > 10 ? 'text-blue-400' : 'text-text-secondary' },
    { label: 'Soil Moisture', value: soilMoisture > 0 ? `${soilMoisture.toFixed(1)}%` : 'N/A', icon: <Gauge className="w-4 h-4" />, color: soilMoisture > 70 ? 'text-blue-400' : 'text-text-secondary' },
  ];

  // Data for charts
  const chartData = {
    temperature: temp,
    humidity,
    wind_speed: windSpd,
    precipitation: precip,
    rain,
    soil_moisture: soilMoisture,
  };

  const radarData = [
    { metric: 'Temperature', value: Math.min(((temp + 10) / 60) * 100, 100) },
    { metric: 'Humidity', value: humidity },
    { metric: 'Wind', value: Math.min((windSpd / 100) * 100, 100) },
    { metric: 'Precipitation', value: Math.min((precip / 50) * 100, 100) },
    { metric: 'Soil Moisture', value: soilMoisture },
  ];

  return (
    <div className="space-y-4 overflow-y-auto max-h-[calc(100vh-140px)] pr-1 scrollbar-thin">
      {/* Current conditions hero */}
      <div className="glass-card p-4 flex items-center gap-4">
        <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-surface-700/60">
          {wxIcon}
        </div>
        <div className="flex-1">
          <p className="text-xl font-bold">{temp.toFixed(1)}°C</p>
          <p className="text-sm text-text-secondary">{wxLabel}</p>
        </div>
        <div className="text-right text-xs text-text-muted">
          <p>{humidity.toFixed(0)}% RH</p>
          <p>{windSpd.toFixed(0)} km/h {windDirection(windDir)}</p>
          {precip > 0 && <p>{precip.toFixed(1)} mm</p>}
        </div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {metrics.map((m) => (
          <div key={m.label} className="glass-card p-3 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-text-muted text-[10px] uppercase tracking-wide">
              {m.icon}
              {m.label}
            </div>
            <p className={`text-sm font-semibold ${m.color}`}>{m.value}</p>
          </div>
        ))}
      </div>

      {/* Climate averages */}
      {soilAnalysis?.climate && (
        <div className="glass-card p-3">
          <p className="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wider">
            Climate Averages
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-text-muted">Mean Annual Temp</span>
              <p className="font-semibold">{soilAnalysis.climate.mean_annual_temp_c.toFixed(1)}°C</p>
            </div>
            <div>
              <span className="text-text-muted">Mean Annual Precip</span>
              <p className="font-semibold">{soilAnalysis.climate.mean_annual_precip_mm.toFixed(0)} mm</p>
            </div>
          </div>
        </div>
      )}

      {/* Charts */}
      {w && (
        <div className="glass-card p-3">
          <p className="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wider">
            Conditions Overview
          </p>
          <WeatherConditionsChart weather={w} />
        </div>
      )}

      {riskAssessment && (
        <div className="glass-card p-3">
          <p className="text-xs font-semibold text-text-secondary mb-2 uppercase tracking-wider">
            Environmental Radar
          </p>
          <EnvironmentalRadarChart assessment={riskAssessment} />
        </div>
      )}

      {/* Data source */}
      <p className="text-[10px] text-text-muted text-center">
        Source: {w?.source ?? 'Open-Meteo'} • Updated {soilAnalysis?.timestamp ? new Date(soilAnalysis.timestamp).toLocaleTimeString() : 'N/A'}
      </p>
    </div>
  );
};

export default WeatherDashboard;
