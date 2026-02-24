"""Flood risk assessment model.

Uses terrain analysis, precipitation data, and soil characteristics
to estimate flood risk and inundation potential.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class FloodModel:
    """Flood risk assessment using hydrological analysis.

    Combines terrain features, precipitation, soil infiltration capacity,
    and proximity to water bodies to estimate flood probability.
    """

    def predict(
        self,
        latitude: float,
        longitude: float,
        elevation: float = 100.0,
        slope: float = 5.0,
        rainfall_mm_24h: float = 30.0,
        rainfall_mm_annual: float = 800.0,
        soil_type: str = "Loam",
        sand_pct: float = 40.0,
        clay_pct: float = 25.0,
        soil_moisture: float = 30.0,
        distance_to_river_km: float = 5.0,
        flow_accumulation: float = 100.0,
        land_cover: str = "cropland",
        ndvi: float = 0.5,
        drainage_density: float = 2.0,
    ) -> Dict[str, Any]:
        """Predict flood risk for a location.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            elevation: Elevation in meters.
            slope: Terrain slope in degrees.
            rainfall_mm_24h: Recent 24h rainfall in mm.
            rainfall_mm_annual: Mean annual rainfall.
            soil_type: USDA soil texture classification.
            sand_pct: Sand content percentage.
            clay_pct: Clay content percentage.
            soil_moisture: Current soil moisture percentage.
            distance_to_river_km: Distance to nearest river/stream.
            flow_accumulation: Upstream catchment area proxy.
            land_cover: Land cover type.
            ndvi: Vegetation index (0-1).
            drainage_density: Drainage density (km/km²).

        Returns:
            Dictionary with flood probability, risk level, and details.
        """
        # Terrain susceptibility
        terrain_score = self._terrain_factor(elevation, slope)

        # Rainfall intensity
        rainfall_score = self._rainfall_factor(
            rainfall_mm_24h, rainfall_mm_annual
        )

        # Soil infiltration capacity
        infiltration_score = self._infiltration_factor(
            sand_pct, clay_pct, soil_moisture
        )

        # Proximity to water
        proximity_score = self._water_proximity_factor(
            distance_to_river_km, flow_accumulation
        )

        # Land cover (impervious surfaces)
        cover_score = self._land_cover_factor(land_cover, ndvi)

        # Drainage
        drainage_score = self._drainage_factor(drainage_density)

        # Weighted combination
        weights = {
            "terrain": 0.20,
            "rainfall": 0.25,
            "infiltration": 0.15,
            "proximity": 0.20,
            "cover": 0.10,
            "drainage": 0.10,
        }

        scores = {
            "terrain": terrain_score,
            "rainfall": rainfall_score,
            "infiltration": infiltration_score,
            "proximity": proximity_score,
            "cover": cover_score,
            "drainage": drainage_score,
        }

        probability = sum(weights[k] * scores[k] for k in weights)
        probability = float(np.clip(probability, 0, 1))

        # Regional adjustment
        probability = self._regional_adjustment(probability, latitude, longitude)

        risk_level = self._classify_risk(probability)

        # Estimate inundation depth
        max_depth = self._estimate_inundation_depth(
            probability, rainfall_mm_24h, slope, elevation
        )

        # Estimate return period
        return_period = self._estimate_return_period(probability)

        return {
            "probability": round(probability, 3),
            "risk_level": risk_level,
            "return_period_years": return_period,
            "max_inundation_depth_m": round(max_depth, 2),
            "factor_scores": {k: round(v, 3) for k, v in scores.items()},
            "contributing_factors": self._get_contributing_factors(scores),
        }

    def _terrain_factor(self, elevation: float, slope: float) -> float:
        """Low-lying flat terrain is most flood-prone."""
        # Low elevation = high risk
        if elevation < 10:
            elev_score = 0.9
        elif elevation < 50:
            elev_score = 0.7
        elif elevation < 200:
            elev_score = 0.4
        elif elevation < 500:
            elev_score = 0.2
        else:
            elev_score = 0.1

        # Flat terrain = high risk
        if slope < 1:
            slope_score = 0.9
        elif slope < 3:
            slope_score = 0.7
        elif slope < 8:
            slope_score = 0.4
        elif slope < 15:
            slope_score = 0.2
        else:
            slope_score = 0.1

        return float(elev_score * 0.5 + slope_score * 0.5)

    def _rainfall_factor(
        self, rainfall_24h: float, annual: float
    ) -> float:
        """Heavy rainfall increases flood risk."""
        # 24h intensity
        if rainfall_24h < 10:
            intensity = 0.05
        elif rainfall_24h < 30:
            intensity = 0.2
        elif rainfall_24h < 50:
            intensity = 0.4
        elif rainfall_24h < 100:
            intensity = 0.6
        elif rainfall_24h < 200:
            intensity = 0.8
        else:
            intensity = 0.95

        # Annual rainfall context
        annual_factor = min(1.0, annual / 2000)

        return float(intensity * 0.7 + annual_factor * 0.3)

    def _infiltration_factor(
        self, sand_pct: float, clay_pct: float, moisture: float
    ) -> float:
        """Low infiltration = more runoff = higher flood risk."""
        # Clay-rich soils have low infiltration
        clay_score = min(1.0, clay_pct / 50)

        # Saturated soil can't absorb more water
        saturation_score = min(1.0, moisture / 60)

        # Sandy soils drain well
        sand_benefit = max(0, 1 - sand_pct / 80)

        return float(clay_score * 0.3 + saturation_score * 0.4 + sand_benefit * 0.3)

    def _water_proximity_factor(
        self, distance_km: float, flow_acc: float
    ) -> float:
        """Closer to rivers and in flow concentration areas = higher risk."""
        if distance_km < 0.5:
            prox = 0.9
        elif distance_km < 1:
            prox = 0.7
        elif distance_km < 3:
            prox = 0.4
        elif distance_km < 10:
            prox = 0.2
        else:
            prox = 0.05

        flow_score = min(1.0, flow_acc / 1000)

        return float(prox * 0.6 + flow_score * 0.4)

    def _land_cover_factor(self, land_cover: str, ndvi: float) -> float:
        """Impervious surfaces increase runoff."""
        cover_runoff = {
            "urban": 0.9, "bare": 0.7, "cropland": 0.5,
            "grassland": 0.3, "shrubland": 0.25,
            "forest": 0.1, "wetland": 0.6, "water": 0.95,
        }
        base = cover_runoff.get(land_cover.lower(), 0.4)
        ndvi_benefit = max(0, (ndvi - 0.3) * 0.5)
        return float(np.clip(base - ndvi_benefit, 0, 1))

    def _drainage_factor(self, density: float) -> float:
        """Higher drainage density can quickly concentrate flow."""
        return float(np.clip(density / 5.0, 0, 1))

    def _regional_adjustment(
        self, prob: float, lat: float, lon: float
    ) -> float:
        """Adjust for known flood-prone regions."""
        # Bangladesh / Ganges delta
        if 20 <= lat <= 27 and 85 <= lon <= 95:
            prob *= 1.3
        # Mississippi delta
        elif 28 <= lat <= 35 and -95 <= lon <= -88:
            prob *= 1.15
        # Netherlands / Low Countries
        elif 51 <= lat <= 54 and 3 <= lon <= 8:
            prob *= 1.1

        return float(np.clip(prob, 0, 0.99))

    def _classify_risk(self, probability: float) -> str:
        """Classify flood risk level."""
        if probability < 0.1:
            return "Very Low"
        elif probability < 0.25:
            return "Low"
        elif probability < 0.45:
            return "Moderate"
        elif probability < 0.65:
            return "High"
        elif probability < 0.8:
            return "Very High"
        return "Extreme"

    def _estimate_inundation_depth(
        self, prob: float, rainfall: float, slope: float, elevation: float
    ) -> float:
        """Rough estimate of maximum flood inundation depth."""
        if prob < 0.1:
            return 0.0
        base_depth = rainfall / 500  # mm to m conversion with absorption
        slope_factor = max(0.1, 1 - slope / 45)
        elev_factor = max(0.2, 1 - elevation / 1000)
        return float(np.clip(base_depth * slope_factor * elev_factor * prob * 5, 0, 10))

    def _estimate_return_period(self, probability: float) -> int:
        """Estimate flood return period in years."""
        if probability < 0.05:
            return 500
        elif probability < 0.1:
            return 200
        elif probability < 0.2:
            return 100
        elif probability < 0.3:
            return 50
        elif probability < 0.5:
            return 25
        elif probability < 0.7:
            return 10
        elif probability < 0.85:
            return 5
        return 2

    def _get_contributing_factors(self, scores: Dict[str, float]) -> list:
        """Get top contributing factors."""
        factor_names = {
            "terrain": "low_elevation_flat_terrain",
            "rainfall": "heavy_precipitation",
            "infiltration": "poor_soil_drainage",
            "proximity": "close_to_water_body",
            "cover": "impervious_surface",
            "drainage": "high_drainage_concentration",
        }
        sorted_factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [factor_names[k] for k, v in sorted_factors[:3] if v > 0.3]


_model_instance: Optional[FloodModel] = None


def get_flood_model() -> FloodModel:
    """Get or create singleton flood model."""
    global _model_instance
    if _model_instance is None:
        _model_instance = FloodModel()
    return _model_instance
