import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  CircleMarker,
  useMapEvents,
  ZoomControl,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import type { Map as LeafletMap } from 'leaflet';
import type { EarthquakeEvent, SoilAnalysis, RiskAssessment } from '../../types';
import MapLegend from './Legend';
import LayerControl from './LayerControl';

// Fix default marker icon
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface MapViewProps {
  earthquakes: EarthquakeEvent[];
  soilAnalysis: SoilAnalysis | null;
  riskAssessment: RiskAssessment | null;
  selectedPoint: [number, number] | null;
  onMapClick: (lat: number, lon: number) => void;
  isLoading: boolean;
  theme?: 'dark' | 'light';
}

function ClickHandler({ onClick }: { onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/** Fly to selected point when it changes */
function FlyToPoint({ point }: { point: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (point) {
      map.flyTo(point, Math.max(map.getZoom(), 8), { duration: 1.2 });
    }
  }, [point, map]);
  return null;
}

function getMagnitudeColor(mag: number): string {
  if (mag >= 7) return '#dc2626';
  if (mag >= 6) return '#ea580c';
  if (mag >= 5) return '#f59e0b';
  if (mag >= 4) return '#eab308';
  if (mag >= 3) return '#84cc16';
  return '#6b7280';
}

function getMagnitudeRadius(mag: number): number {
  return Math.max(4, mag * 3);
}

function getRiskColor(level: string): string {
  switch (level?.toLowerCase()) {
    case 'critical': case 'severe': case 'very high': return '#dc2626';
    case 'high': return '#ea580c';
    case 'moderate': case 'medium': return '#f59e0b';
    case 'low': return '#22c55e';
    case 'very low': case 'minimal': return '#3b82f6';
    default: return '#6b7280';
  }
}

function getHealthColor(score: number): string {
  if (score >= 70) return '#22c55e';
  if (score >= 50) return '#f59e0b';
  return '#dc2626';
}

const MapView: React.FC<MapViewProps> = ({
  earthquakes,
  soilAnalysis,
  riskAssessment,
  selectedPoint,
  onMapClick,
  isLoading,
  theme = 'dark',
}) => {
  const mapRef = useRef<LeafletMap | null>(null);
  const [layers, setLayers] = useState({
    earthquakes: true,
    soilHealth: true,
    riskZones: true,
    terrain: false,
  });

  const handleLayerToggle = useCallback((layerId: string) => {
    setLayers((prev) => ({ ...prev, [layerId]: !prev[layerId as keyof typeof prev] }));
  }, []);

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={[20, 0]}
        zoom={3}
        zoomControl={false}
        className="w-full h-full z-0"
        ref={mapRef}
        maxZoom={18}
        minZoom={2}
        worldCopyJump
      >
        <ZoomControl position="bottomright" />
        <ClickHandler onClick={onMapClick} />
        <FlyToPoint point={selectedPoint} />

        {/* Base tile layer */}
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url={
            theme === 'dark'
              ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
              : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
          }
          key={`base-${theme}`}
        />

        {/* Optional terrain layer */}
        {layers.terrain && (
          <TileLayer
            attribution='&copy; <a href="https://www.opentopomap.org/">OpenTopoMap</a>'
            url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
            opacity={0.5}
          />
        )}

        {/* Selected Point Marker */}
        {selectedPoint && (
          <Marker position={selectedPoint}>
            <Popup>
              <div className="text-sm" style={{ minWidth: 180 }}>
                <p className="font-bold">Selected Location</p>
                <p className="font-mono text-xs">
                  {selectedPoint[0].toFixed(5)}, {selectedPoint[1].toFixed(5)}
                </p>
                {isLoading && (
                  <p className="text-blue-500 mt-1 flex items-center gap-1">
                    <span className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin inline-block" />
                    Analyzing…
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        )}

        {/* Soil Analysis Circle */}
        {layers.soilHealth && soilAnalysis && (
          <CircleMarker
            center={[soilAnalysis.location.latitude, soilAnalysis.location.longitude]}
            radius={14}
            fillColor={getHealthColor(soilAnalysis.health_index.score)}
            fillOpacity={0.6}
            color="#fff"
            weight={2}
          >
            <Popup>
              <div className="text-sm" style={{ minWidth: 200, maxWidth: 280 }}>
                <p className="font-bold text-base">
                  Soil Health: {soilAnalysis.health_index.grade}
                </p>
                <p>Score: {soilAnalysis.health_index.score.toFixed(0)}/100 — {soilAnalysis.health_index.category}</p>
                <hr className="my-1" />
                <table className="w-full text-xs">
                  <tbody>
                    <tr><td className="py-0.5">pH</td><td className="text-right">{soilAnalysis.soil_properties.ph.value.toFixed(2)}</td></tr>
                    <tr><td className="py-0.5">Organic C</td><td className="text-right">{soilAnalysis.soil_properties.organic_carbon_pct.value.toFixed(2)}%</td></tr>
                    <tr><td className="py-0.5">Nitrogen</td><td className="text-right">{soilAnalysis.soil_properties.nitrogen_pct.value.toFixed(3)}%</td></tr>
                    <tr><td className="py-0.5">Texture</td><td className="text-right">{soilAnalysis.soil_properties.texture.classification}</td></tr>
                    <tr><td className="py-0.5">Erosion</td><td className="text-right">{soilAnalysis.erosion_risk.risk_level} ({soilAnalysis.erosion_risk.rusle_value_tons_ha_yr.toFixed(1)} t/ha/yr)</td></tr>
                    <tr><td className="py-0.5">NDVI</td><td className="text-right">{soilAnalysis.metadata?.ndvi?.toFixed(3) ?? 'N/A'}</td></tr>
                  </tbody>
                </table>
              </div>
            </Popup>
          </CircleMarker>
        )}

        {/* Risk Overlay */}
        {layers.riskZones && riskAssessment && (
          <>
            {/* Outer risk ring */}
            <CircleMarker
              center={[riskAssessment.location.latitude, riskAssessment.location.longitude]}
              radius={25}
              fillColor={getRiskColor(riskAssessment.composite_risk_level)}
              fillOpacity={0.15}
              color={getRiskColor(riskAssessment.composite_risk_level)}
              weight={1}
              dashArray="8,4"
            />
            {/* Inner risk core */}
            <CircleMarker
              center={[riskAssessment.location.latitude, riskAssessment.location.longitude]}
              radius={12}
              fillColor={getRiskColor(riskAssessment.composite_risk_level)}
              fillOpacity={0.35}
              color={getRiskColor(riskAssessment.composite_risk_level)}
              weight={2}
            >
              <Popup>
                <div className="text-sm" style={{ minWidth: 200, maxWidth: 280 }}>
                  <p className="font-bold text-base">Risk Assessment</p>
                  <p>
                    Composite: <strong>{riskAssessment.composite_risk_level}</strong>{' '}
                    ({riskAssessment.composite_risk_score}%)
                  </p>
                  <hr className="my-1" />
                  <table className="w-full text-xs">
                    <tbody>
                      <tr><td className="py-0.5">Landslide</td><td className="text-right">{riskAssessment.risks.landslide.risk_level} ({(riskAssessment.risks.landslide.probability * 100).toFixed(0)}%)</td></tr>
                      <tr><td className="py-0.5">Flood</td><td className="text-right">{riskAssessment.risks.flood.risk_level} ({(riskAssessment.risks.flood.probability * 100).toFixed(0)}%)</td></tr>
                      <tr><td className="py-0.5">Wildfire</td><td className="text-right">{riskAssessment.risks.wildfire.risk_level} ({(riskAssessment.risks.wildfire.probability * 100).toFixed(0)}%)</td></tr>
                      <tr><td className="py-0.5">Liquefaction</td><td className="text-right">{riskAssessment.risks.liquefaction.susceptibility}</td></tr>
                    </tbody>
                  </table>
                  {riskAssessment.current_conditions && (
                    <>
                      <hr className="my-1" />
                      <p className="text-[10px] text-gray-400">
                        {riskAssessment.current_conditions.temperature_c?.toFixed(1)}°C,{' '}
                        {riskAssessment.current_conditions.humidity_pct?.toFixed(0)}% RH,{' '}
                        Wind {riskAssessment.current_conditions.wind_speed_kmh?.toFixed(0)} km/h
                      </p>
                    </>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          </>
        )}

        {/* Earthquake Markers */}
        {layers.earthquakes &&
          earthquakes.map((eq) => (
            <CircleMarker
              key={eq.event_id}
              center={[eq.latitude, eq.longitude]}
              radius={getMagnitudeRadius(eq.magnitude)}
              fillColor={getMagnitudeColor(eq.magnitude)}
              fillOpacity={0.7}
              color={getMagnitudeColor(eq.magnitude)}
              weight={1}
              className={eq.magnitude >= 5 ? 'pulse-marker' : ''}
            >
              <Popup>
                <div className="text-sm" style={{ minWidth: 200, maxWidth: 280 }}>
                  <p className="font-bold">
                    M{eq.magnitude.toFixed(1)} {eq.magnitude_type}
                  </p>
                  <p>{eq.place}</p>
                  <p className="text-xs">Depth: {eq.depth_km.toFixed(1)} km</p>
                  <p className="text-xs">Time: {new Date(eq.event_time).toLocaleString()}</p>
                  {eq.felt != null && eq.felt > 0 && (
                    <p className="text-xs">Felt by: {eq.felt} reports</p>
                  )}
                  {eq.significance > 0 && (
                    <p className="text-xs">Significance: {eq.significance}</p>
                  )}
                  {eq.tsunami && (
                    <p className="text-red-500 font-bold mt-1">⚠ Tsunami Warning</p>
                  )}
                  <a
                    href={eq.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 underline mt-1 block text-xs"
                  >
                    USGS Details →
                  </a>
                </div>
              </Popup>
            </CircleMarker>
          ))}
      </MapContainer>

      {/* Layer Control */}
      <div className="absolute top-3 right-3 sm:top-4 sm:right-4 z-[1000]">
        <LayerControl layers={layers} onToggle={handleLayerToggle} />
      </div>

      {/* Legend (hidden on very small screens, togglable) */}
      <div className="absolute bottom-16 sm:bottom-8 left-3 sm:left-4 z-[1000]">
        <MapLegend />
      </div>

      {/* Coordinates display for selected point (mobile) */}
      {selectedPoint && (
        <div className="sm:hidden absolute top-3 left-3 z-[1000] coord-chip text-[10px]">
          {selectedPoint[0].toFixed(4)}, {selectedPoint[1].toFixed(4)}
        </div>
      )}

      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute top-3 sm:top-4 left-1/2 -translate-x-1/2 z-[1000] glass-card px-4 py-2 flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs sm:text-sm text-text-secondary">Analyzing location…</span>
        </div>
      )}
    </div>
  );
};

export default MapView;
