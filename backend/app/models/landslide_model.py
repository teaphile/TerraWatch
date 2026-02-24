"""Landslide susceptibility prediction model.

Uses ensemble methods to predict landslide probability based on
terrain, soil, climate, and land cover features.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class LandslideModel:
    """Landslide susceptibility prediction using analytical methods.

    Combines multiple geomorphological and environmental factors
    to estimate landslide probability for any given location.
    """

    def predict(
        self,
        latitude: float,
        longitude: float,
        elevation: float = 100.0,
        slope: float = 10.0,
        aspect: float = 180.0,
        curvature: float = 0.0,
        soil_moisture: float = 30.0,
        soil_type: str = "Loam",
        clay_pct: float = 25.0,
        rainfall_mm: float = 50.0,
        ndvi: float = 0.5,
        distance_to_fault_km: float = 50.0,
        distance_to_river_km: float = 5.0,
        land_cover: str = "forest",
        lithology: str = "sedimentary",
    ) -> Dict[str, Any]:
        """Predict landslide susceptibility for a location.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            elevation: Elevation in meters.
            slope: Slope angle in degrees.
            aspect: Slope aspect in degrees (0-360).
            curvature: Terrain curvature.
            soil_moisture: Current soil moisture percentage.
            soil_type: USDA soil texture classification.
            clay_pct: Clay content percentage.
            rainfall_mm: Recent rainfall in mm (last 24-72h).
            ndvi: Vegetation index (0-1).
            distance_to_fault_km: Distance to nearest fault line.
            distance_to_river_km: Distance to nearest river.
            land_cover: Land cover type.
            lithology: Rock/geological type.

        Returns:
            Dictionary with probability, risk level, and contributing factors.
        """
        # Calculate individual factor scores (0-1)
        slope_score = self._slope_factor(slope)
        aspect_score = self._aspect_factor(aspect)
        curvature_score = self._curvature_factor(curvature)
        elevation_score = self._elevation_factor(elevation)
        soil_score = self._soil_factor(soil_type, clay_pct, soil_moisture)
        rainfall_score = self._rainfall_factor(rainfall_mm)
        vegetation_score = self._vegetation_factor(ndvi, land_cover)
        fault_score = self._fault_proximity_factor(distance_to_fault_km)
        river_score = self._river_proximity_factor(distance_to_river_km)
        lithology_score = self._lithology_factor(lithology)

        # Weighted combination
        weights = {
            "slope": 0.25,
            "rainfall": 0.18,
            "soil": 0.15,
            "vegetation": 0.10,
            "lithology": 0.08,
            "curvature": 0.07,
            "fault": 0.06,
            "river": 0.04,
            "elevation": 0.04,
            "aspect": 0.03,
        }

        scores = {
            "slope": slope_score,
            "rainfall": rainfall_score,
            "soil": soil_score,
            "vegetation": vegetation_score,
            "lithology": lithology_score,
            "curvature": curvature_score,
            "fault": fault_score,
            "river": river_score,
            "elevation": elevation_score,
            "aspect": aspect_score,
        }

        probability = sum(weights[k] * scores[k] for k in weights)
        probability = float(np.clip(probability, 0, 1))

        # Regional adjustment for known high-risk areas
        probability = self._apply_regional_adjustment(
            probability, latitude, longitude
        )

        risk_level = self._classify_risk(probability)
        contributing = self._get_contributing_factors(scores)

        return {
            "probability": round(probability, 3),
            "risk_level": risk_level,
            "contributing_factors": contributing,
            "factor_scores": {k: round(v, 3) for k, v in scores.items()},
        }

    def _slope_factor(self, slope: float) -> float:
        """Steeper slopes = higher risk. Critical threshold ~30-45°."""
        if slope < 5:
            return 0.05
        elif slope < 15:
            return 0.15 + (slope - 5) / 10 * 0.2
        elif slope < 30:
            return 0.35 + (slope - 15) / 15 * 0.3
        elif slope < 45:
            return 0.65 + (slope - 30) / 15 * 0.25
        return 0.9

    def _aspect_factor(self, aspect: float) -> float:
        """South-facing slopes (N. hemisphere) have higher risk due to drying cycles."""
        # Normalize to 0-1 (south-facing = higher)
        return 0.3 + 0.4 * abs(math.sin(math.radians(aspect)))

    def _curvature_factor(self, curvature: float) -> float:
        """Concave slopes concentrate water flow."""
        if curvature < -2:
            return 0.8
        elif curvature < 0:
            return 0.5 + abs(curvature) * 0.15
        elif curvature < 2:
            return 0.3
        return 0.2  # Convex = lower risk

    def _elevation_factor(self, elevation: float) -> float:
        """Mid-elevation zones (500-2000m) have highest risk."""
        if elevation < 200:
            return 0.2
        elif elevation < 500:
            return 0.4
        elif elevation < 1500:
            return 0.6
        elif elevation < 3000:
            return 0.7
        return 0.5

    def _soil_factor(
        self, soil_type: str, clay_pct: float, moisture: float
    ) -> float:
        """Clay-rich, saturated soils are most susceptible."""
        type_risk = {
            "Clay": 0.8, "Silty Clay": 0.75, "Sandy Clay": 0.7,
            "Clay Loam": 0.6, "Silty Clay Loam": 0.55,
            "Loam": 0.4, "Silt Loam": 0.45,
            "Sandy Loam": 0.3, "Sand": 0.2,
        }
        base = type_risk.get(soil_type, 0.4)

        # High moisture increases risk
        moisture_factor = min(1.0, moisture / 80.0)
        # Clay content adjustment
        clay_factor = min(1.0, clay_pct / 50.0)

        return float(np.clip(base * 0.4 + moisture_factor * 0.35 + clay_factor * 0.25, 0, 1))

    def _rainfall_factor(self, rainfall_mm: float) -> float:
        """Heavy rainfall significantly increases risk."""
        if rainfall_mm < 10:
            return 0.05
        elif rainfall_mm < 30:
            return 0.15
        elif rainfall_mm < 50:
            return 0.3
        elif rainfall_mm < 100:
            return 0.5
        elif rainfall_mm < 200:
            return 0.75
        return 0.9

    def _vegetation_factor(self, ndvi: float, land_cover: str) -> float:
        """Dense vegetation stabilizes slopes, bare land increases risk."""
        cover_risk = {
            "forest": 0.1, "grassland": 0.3, "shrubland": 0.25,
            "cropland": 0.5, "bare": 0.9, "urban": 0.3,
        }
        base = cover_risk.get(land_cover.lower(), 0.4)
        ndvi_factor = max(0, 1.0 - ndvi * 1.5)
        return float(np.clip(base * 0.5 + ndvi_factor * 0.5, 0, 1))

    def _fault_proximity_factor(self, distance_km: float) -> float:
        """Closer to faults = higher seismic triggering risk."""
        if distance_km < 5:
            return 0.9
        elif distance_km < 20:
            return 0.6
        elif distance_km < 50:
            return 0.3
        return 0.1

    def _river_proximity_factor(self, distance_km: float) -> float:
        """River undercutting destabilizes slopes."""
        if distance_km < 0.5:
            return 0.8
        elif distance_km < 2:
            return 0.5
        elif distance_km < 5:
            return 0.3
        return 0.1

    def _lithology_factor(self, lithology: str) -> float:
        """Some rock types are more susceptible to landslides."""
        lithology_risk = {
            "sedimentary": 0.6, "metamorphic": 0.5,
            "volcanic": 0.7, "igneous": 0.3,
            "shale": 0.8, "limestone": 0.5,
            "sandstone": 0.6, "granite": 0.2,
            "clay": 0.85, "loose": 0.9,
        }
        return lithology_risk.get(lithology.lower(), 0.5)

    def _apply_regional_adjustment(
        self, prob: float, lat: float, lon: float
    ) -> float:
        """Adjust probability for known high-risk regions."""
        # Himalayan region
        if 25 <= lat <= 38 and 70 <= lon <= 100:
            prob *= 1.2
        # Japanese Alps
        elif 33 <= lat <= 43 and 129 <= lon <= 146:
            prob *= 1.15
        # Andes
        elif -40 <= lat <= 10 and -80 <= lon <= -65:
            prob *= 1.15
        # European Alps
        elif 43 <= lat <= 48 and 5 <= lon <= 17:
            prob *= 1.1

        return float(np.clip(prob, 0, 0.99))

    def _classify_risk(self, probability: float) -> str:
        """Classify landslide risk from probability."""
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

    def _get_contributing_factors(
        self, scores: Dict[str, float]
    ) -> List[str]:
        """Get top contributing factors."""
        factor_names = {
            "slope": "steep_slope",
            "rainfall": "heavy_rainfall",
            "soil": "unstable_soil",
            "vegetation": "poor_vegetation_cover",
            "lithology": "susceptible_geology",
            "curvature": "concave_terrain",
            "fault": "fault_proximity",
            "river": "river_undercutting",
            "elevation": "elevation_zone",
            "aspect": "slope_orientation",
        }

        sorted_factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [factor_names[k] for k, v in sorted_factors[:3] if v > 0.3]


_model_instance: Optional[LandslideModel] = None


def get_landslide_model() -> LandslideModel:
    """Get or create singleton landslide model."""
    global _model_instance
    if _model_instance is None:
        _model_instance = LandslideModel()
    return _model_instance
