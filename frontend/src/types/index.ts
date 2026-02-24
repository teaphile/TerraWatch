/**
 * TypeScript interfaces for TerraWatch.
 */

export interface Location {
  latitude: number;
  longitude: number;
  elevation_m?: number;
  country?: string;
  region?: string;
}

export interface SoilProperty {
  value: number;
  confidence?: number;
  category?: string;
}

export interface SoilTexture {
  sand_pct: number;
  silt_pct: number;
  clay_pct: number;
  classification: string;
}

export interface SoilMoisture {
  surface_0_1cm: number | null;
  shallow_1_3cm: number | null;
  mid_3_9cm: number | null;
  deep_9_27cm: number | null;
  average_pct: number;
  source: string;
}

export interface ErosionRisk {
  rusle_value_tons_ha_yr: number;
  risk_level: string;
  factors: {
    R: number;
    K: number;
    LS: number;
    C: number;
    P: number;
  };
}

export interface HealthIndex {
  score: number;
  grade: string;
  category: string;
}

export interface CarbonSequestration {
  current_stock_tons_ha: number;
  potential_stock_tons_ha: number;
  improvement_potential_pct: number;
  management_factor: number;
}

export interface SoilAnalysis {
  location: Location;
  soil_properties: {
    ph: SoilProperty;
    organic_carbon_pct: SoilProperty;
    nitrogen_pct: SoilProperty;
    moisture_pct: SoilProperty;
    texture: SoilTexture;
    bulk_density_gcm3: number;
    cec_cmolkg: number;
  };
  soil_moisture: SoilMoisture;
  health_index: HealthIndex;
  erosion_risk: ErosionRisk;
  carbon_sequestration: CarbonSequestration;
  climate: {
    mean_annual_temp_c: number;
    mean_annual_precip_mm: number;
    current_weather: WeatherData;
  };
  metadata: {
    ndvi: number;
    slope_degrees: number;
    land_cover: string;
  };
  timestamp: string;
}

export interface WeatherData {
  temperature_c: number;
  humidity_pct: number;
  precipitation_mm: number;
  rain_mm: number;
  wind_speed_kmh: number;
  wind_direction_deg: number;
  weather_code: number;
  source: string;
}

export interface RiskLevel {
  probability: number;
  risk_level: string;
  contributing_factors?: string[];
}

export interface FloodRisk extends RiskLevel {
  return_period_years: number;
  max_inundation_depth_m: number;
}

export interface LiquefactionRisk {
  susceptibility: string;
  probability_given_m7: number;
  soil_type_factor: string;
}

export interface WildfireRisk extends RiskLevel {
  vegetation_dryness_index: number;
}

export interface RiskAssessment {
  location: { latitude: number; longitude: number };
  risks: {
    landslide: RiskLevel;
    flood: FloodRisk;
    liquefaction: LiquefactionRisk;
    wildfire: WildfireRisk;
  };
  composite_risk_score: number;
  composite_risk_level: string;
  active_alerts: Alert[];
  current_conditions: {
    temperature_c: number;
    humidity_pct: number;
    wind_speed_kmh: number;
    precipitation_mm: number;
    soil_moisture_pct: number;
  };
  timestamp: string;
}

export interface EarthquakeEvent {
  event_id: string;
  latitude: number;
  longitude: number;
  depth_km: number;
  magnitude: number;
  magnitude_type: string;
  place: string;
  event_time: string;
  url: string;
  felt: number | null;
  tsunami: boolean;
  alert_level: string | null;
  significance: number;
}

export interface Alert {
  id: string;
  type: string;
  severity: 'critical' | 'warning' | 'watch' | 'advisory';
  title: string;
  description: string;
  latitude: number | null;
  longitude: number | null;
  radius_km: number | null;
  data: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  expires_at: string;
}

export interface ApiResponse<T> {
  status: string;
  data: T;
}

export interface MapLayer {
  id: string;
  name: string;
  visible: boolean;
  opacity: number;
  color: string;
}

export interface Recommendation {
  category: string;
  priority?: string;
  title?: string;
  description: string;
  actions?: string[];
}

export interface AgricultureRecommendations {
  suitable_crops: Array<{
    crop: string;
    suitability_score: number;
    suitability: string;
  }>;
  fertilizer_recommendations: Array<{
    nutrient: string;
    status: string;
    recommendation: string;
    organic_alternative: string;
  }>;
  irrigation_schedule: {
    water_holding_capacity: string;
    current_moisture_pct: number;
    irrigation_frequency: string;
    irrigation_depth: string;
    urgency: string;
    method: string;
    best_time: string;
  };
  soil_amendments: Array<{
    amendment: string;
    purpose: string;
    application_rate: string;
  }>;
  summary: string;
}
