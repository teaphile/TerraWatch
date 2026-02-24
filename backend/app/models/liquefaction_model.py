"""Earthquake soil liquefaction susceptibility model.

Assesses the likelihood of soil liquefaction during seismic events
based on soil type, groundwater conditions, and seismic intensity.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class LiquefactionModel:
    """Soil liquefaction susceptibility assessment.

    Evaluates liquefaction potential based on soil composition,
    groundwater depth, and expected seismic intensity.
    """

    def predict(
        self,
        sand_pct: float = 40.0,
        silt_pct: float = 35.0,
        clay_pct: float = 25.0,
        soil_type: str = "Loam",
        groundwater_depth_m: float = 5.0,
        soil_moisture: float = 30.0,
        bulk_density: float = 1.35,
        recent_earthquake_magnitude: float = 0.0,
        distance_to_epicenter_km: float = 100.0,
        peak_ground_acceleration: float = 0.0,
    ) -> Dict[str, Any]:
        """Assess liquefaction susceptibility.

        Args:
            sand_pct: Sand content percentage.
            silt_pct: Silt content percentage.
            clay_pct: Clay content percentage.
            soil_type: USDA soil texture classification.
            groundwater_depth_m: Depth to groundwater in meters.
            soil_moisture: Current soil moisture percentage.
            bulk_density: Soil bulk density (g/cm³).
            recent_earthquake_magnitude: Recent earthquake magnitude.
            distance_to_epicenter_km: Distance to recent earthquake.
            peak_ground_acceleration: PGA in g units.

        Returns:
            Dict with susceptibility rating and probability.
        """
        # Soil composition susceptibility
        soil_score = self._soil_composition_factor(
            sand_pct, silt_pct, clay_pct, soil_type
        )

        # Groundwater factor
        gw_score = self._groundwater_factor(groundwater_depth_m, soil_moisture)

        # Density factor
        density_score = self._density_factor(bulk_density)

        # Seismic demand
        seismic_score = self._seismic_factor(
            recent_earthquake_magnitude,
            distance_to_epicenter_km,
            peak_ground_acceleration,
        )

        # Overall susceptibility (without seismic trigger)
        susceptibility = (
            soil_score * 0.40 + gw_score * 0.35 + density_score * 0.25
        )

        # Probability given M7 earthquake at 50km
        prob_m7 = self._probability_given_earthquake(
            susceptibility, 7.0, 50.0
        )

        # Actual probability if recent earthquake
        actual_prob = 0.0
        if recent_earthquake_magnitude > 0:
            actual_prob = self._probability_given_earthquake(
                susceptibility,
                recent_earthquake_magnitude,
                distance_to_epicenter_km,
            )

        susceptibility_class = self._classify_susceptibility(susceptibility)

        return {
            "susceptibility": susceptibility_class,
            "susceptibility_score": round(float(susceptibility), 3),
            "probability_given_m7": round(float(prob_m7), 3),
            "actual_probability": round(float(actual_prob), 3),
            "soil_type_factor": soil_type,
            "factors": {
                "soil_composition": round(float(soil_score), 3),
                "groundwater": round(float(gw_score), 3),
                "density": round(float(density_score), 3),
                "seismic_demand": round(float(seismic_score), 3),
            },
        }

    def _soil_composition_factor(
        self,
        sand_pct: float,
        silt_pct: float,
        clay_pct: float,
        soil_type: str,
    ) -> float:
        """Sandy, loose soils are most susceptible to liquefaction."""
        # High sand content = high susceptibility
        sand_score = min(1.0, sand_pct / 80)

        # Clay inhibits liquefaction
        clay_penalty = max(0, 1 - clay_pct / 30)

        # Fine silt also susceptible
        silt_score = min(0.6, silt_pct / 100)

        # Named soil type adjustment
        type_scores = {
            "Sand": 0.9, "Loamy Sand": 0.8, "Sandy Loam": 0.6,
            "Loam": 0.4, "Silt Loam": 0.5, "Silt": 0.55,
            "Sandy Clay Loam": 0.35, "Clay Loam": 0.2,
            "Silty Clay Loam": 0.15, "Sandy Clay": 0.25,
            "Silty Clay": 0.1, "Clay": 0.05,
        }
        type_score = type_scores.get(soil_type, 0.4)

        return float(np.clip(
            sand_score * 0.3 + clay_penalty * 0.25 +
            silt_score * 0.15 + type_score * 0.3,
            0, 1
        ))

    def _groundwater_factor(
        self, depth_m: float, moisture: float
    ) -> float:
        """Shallow groundwater increases liquefaction risk."""
        if depth_m < 1:
            gw = 0.95
        elif depth_m < 3:
            gw = 0.7
        elif depth_m < 5:
            gw = 0.5
        elif depth_m < 10:
            gw = 0.25
        else:
            gw = 0.1

        moisture_factor = min(1.0, moisture / 60)

        return float(gw * 0.7 + moisture_factor * 0.3)

    def _density_factor(self, bulk_density: float) -> float:
        """Loose soils (low density) are more susceptible."""
        if bulk_density < 1.2:
            return 0.8
        elif bulk_density < 1.4:
            return 0.5
        elif bulk_density < 1.6:
            return 0.3
        return 0.1

    def _seismic_factor(
        self,
        magnitude: float,
        distance_km: float,
        pga: float,
    ) -> float:
        """Calculate seismic demand factor."""
        if magnitude <= 0 and pga <= 0:
            return 0.0

        if pga > 0:
            if pga > 0.4:
                return 0.95
            elif pga > 0.2:
                return 0.7
            elif pga > 0.1:
                return 0.4
            return 0.15

        # Estimate PGA from magnitude and distance
        if distance_km < 1:
            distance_km = 1
        estimated_pga = (10 ** (magnitude * 0.5 - 1.5)) / (distance_km ** 0.5)
        return float(np.clip(estimated_pga, 0, 1))

    def _probability_given_earthquake(
        self,
        susceptibility: float,
        magnitude: float,
        distance_km: float,
    ) -> float:
        """Calculate liquefaction probability for a given earthquake."""
        if distance_km < 1:
            distance_km = 1

        # Seismic loading factor
        loading = (10 ** (magnitude * 0.4 - 1.2)) / (distance_km ** 0.4)
        loading = min(1.0, loading)

        probability = susceptibility * loading
        return float(np.clip(probability, 0, 0.99))

    def _classify_susceptibility(self, score: float) -> str:
        """Classify liquefaction susceptibility."""
        if score < 0.15:
            return "Very Low"
        elif score < 0.3:
            return "Low"
        elif score < 0.5:
            return "Moderate"
        elif score < 0.7:
            return "High"
        return "Very High"


_model_instance: Optional[LiquefactionModel] = None


def get_liquefaction_model() -> LiquefactionModel:
    """Get or create singleton liquefaction model."""
    global _model_instance
    if _model_instance is None:
        _model_instance = LiquefactionModel()
    return _model_instance
