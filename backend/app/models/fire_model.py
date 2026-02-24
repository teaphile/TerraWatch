"""Wildfire risk assessment model.

Evaluates wildfire probability using vegetation dryness, soil moisture,
weather conditions, and topographic factors.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class FireModel:
    """Wildfire risk prediction model.

    Combines fuel moisture, weather, terrain, and historical fire
    data to estimate wildfire probability and potential spread.
    """

    def predict(
        self,
        latitude: float,
        longitude: float,
        temperature_c: float = 25.0,
        humidity_pct: float = 50.0,
        wind_speed_kmh: float = 15.0,
        ndvi: float = 0.5,
        soil_moisture: float = 30.0,
        rainfall_last_7d_mm: float = 20.0,
        slope: float = 5.0,
        elevation: float = 300.0,
        land_cover: str = "forest",
        days_since_rain: int = 3,
    ) -> Dict[str, Any]:
        """Predict wildfire risk for a location.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            temperature_c: Current temperature in Celsius.
            humidity_pct: Relative humidity percentage.
            wind_speed_kmh: Wind speed in km/h.
            ndvi: Vegetation index (0-1).
            soil_moisture: Soil moisture percentage.
            rainfall_last_7d_mm: Rainfall in last 7 days.
            slope: Terrain slope in degrees.
            elevation: Elevation in meters.
            land_cover: Land cover type.
            days_since_rain: Days since last significant rainfall.

        Returns:
            Dictionary with fire probability, risk level, and factors.
        """
        # Vegetation dryness / fuel moisture
        fuel_score = self._fuel_moisture_factor(
            ndvi, soil_moisture, rainfall_last_7d_mm, days_since_rain
        )

        # Weather conditions
        weather_score = self._weather_factor(
            temperature_c, humidity_pct, wind_speed_kmh
        )

        # Terrain
        terrain_score = self._terrain_factor(slope, elevation, latitude)

        # Land cover / fuel type
        fuel_type_score = self._fuel_type_factor(land_cover)

        # Weighted combination
        weights = {
            "fuel_moisture": 0.30,
            "weather": 0.30,
            "terrain": 0.15,
            "fuel_type": 0.25,
        }

        scores = {
            "fuel_moisture": fuel_score,
            "weather": weather_score,
            "terrain": terrain_score,
            "fuel_type": fuel_type_score,
        }

        probability = sum(weights[k] * scores[k] for k in weights)

        # Seasonal adjustment
        probability = self._seasonal_adjustment(probability, latitude)

        probability = float(np.clip(probability, 0, 0.99))
        risk_level = self._classify_risk(probability)

        # Vegetation dryness index
        vdi = self._vegetation_dryness_index(
            ndvi, soil_moisture, temperature_c, humidity_pct
        )

        # Fire Weather Index components
        fwi = self._fire_weather_index(
            temperature_c, humidity_pct, wind_speed_kmh, rainfall_last_7d_mm
        )

        return {
            "probability": round(probability, 3),
            "risk_level": risk_level,
            "vegetation_dryness_index": round(vdi, 2),
            "fire_weather_index": round(fwi, 1),
            "factor_scores": {k: round(v, 3) for k, v in scores.items()},
            "spread_potential": self._spread_potential(
                wind_speed_kmh, slope, fuel_score
            ),
            "contributing_factors": self._get_contributing_factors(scores),
        }

    def _fuel_moisture_factor(
        self,
        ndvi: float,
        soil_moisture: float,
        rainfall_7d: float,
        days_since_rain: int,
    ) -> float:
        """Dry fuel = high fire risk."""
        # Drought stress on vegetation
        moisture_deficit = max(0, 1 - soil_moisture / 50)

        # Days without rain
        dry_spell = min(1.0, days_since_rain / 30)

        # Recent rainfall benefit
        rain_benefit = min(0.5, rainfall_7d / 50)

        # Dead fuel vs live fuel (from NDVI)
        dead_fuel = max(0, 0.8 - ndvi)

        score = (moisture_deficit * 0.3 + dry_spell * 0.3 +
                 dead_fuel * 0.2 + (0.5 - rain_benefit) * 0.2)
        return float(np.clip(score, 0, 1))

    def _weather_factor(
        self,
        temp: float,
        humidity: float,
        wind: float,
    ) -> float:
        """Hot, dry, windy conditions promote fire."""
        # Temperature
        if temp > 40:
            temp_score = 0.95
        elif temp > 35:
            temp_score = 0.8
        elif temp > 30:
            temp_score = 0.6
        elif temp > 25:
            temp_score = 0.4
        elif temp > 15:
            temp_score = 0.2
        else:
            temp_score = 0.05

        # Low humidity
        humidity_score = max(0, 1 - humidity / 80)

        # Wind speed
        if wind > 60:
            wind_score = 0.95
        elif wind > 40:
            wind_score = 0.8
        elif wind > 25:
            wind_score = 0.6
        elif wind > 15:
            wind_score = 0.3
        else:
            wind_score = 0.1

        return float(temp_score * 0.35 + humidity_score * 0.35 + wind_score * 0.3)

    def _terrain_factor(
        self, slope: float, elevation: float, latitude: float
    ) -> float:
        """Upslope fires spread faster."""
        slope_score = min(1.0, slope / 45)

        # Mid-elevation (dry forests)
        if 500 < elevation < 2000:
            elev_score = 0.6
        elif elevation < 500:
            elev_score = 0.4
        else:
            elev_score = 0.3

        return float(slope_score * 0.6 + elev_score * 0.4)

    def _fuel_type_factor(self, land_cover: str) -> float:
        """Different vegetation types have different fire risk."""
        fuel_risk = {
            "forest": 0.7,
            "dense_forest": 0.6,
            "shrubland": 0.8,
            "grassland": 0.75,
            "cropland": 0.4,
            "bare": 0.05,
            "urban": 0.15,
            "water": 0.0,
            "wetland": 0.1,
        }
        return fuel_risk.get(land_cover.lower(), 0.4)

    def _seasonal_adjustment(self, prob: float, latitude: float) -> float:
        """Adjust for fire season based on hemisphere and latitude."""
        import datetime
        month = datetime.datetime.now().month

        if latitude > 0:  # Northern hemisphere
            # Fire season: June-October
            if 6 <= month <= 10:
                prob *= 1.2
            elif month in (4, 5, 11):
                prob *= 1.0
            else:
                prob *= 0.6
        else:  # Southern hemisphere
            # Fire season: December-March
            if month in (12, 1, 2, 3):
                prob *= 1.2
            elif month in (10, 11, 4):
                prob *= 1.0
            else:
                prob *= 0.6

        return prob

    def _vegetation_dryness_index(
        self,
        ndvi: float,
        moisture: float,
        temp: float,
        humidity: float,
    ) -> float:
        """Calculate vegetation dryness index (0-1, higher = drier)."""
        vdi = (
            (1 - ndvi) * 0.3 +
            (1 - moisture / 60) * 0.3 +
            min(1, temp / 45) * 0.2 +
            (1 - humidity / 100) * 0.2
        )
        return float(np.clip(vdi, 0, 1))

    def _fire_weather_index(
        self,
        temp: float,
        humidity: float,
        wind: float,
        rain_7d: float,
    ) -> float:
        """Simplified Fire Weather Index (0-100 scale)."""
        temp_component = max(0, (temp - 10) * 2)
        humidity_component = max(0, (100 - humidity))
        wind_component = wind * 0.5
        rain_component = max(0, 30 - rain_7d)

        fwi = (temp_component + humidity_component +
               wind_component + rain_component) / 4
        return float(np.clip(fwi, 0, 100))

    def _spread_potential(
        self, wind: float, slope: float, fuel: float
    ) -> str:
        """Estimate fire spread potential."""
        spread = wind * 0.4 + slope * 0.3 + fuel * 30
        if spread > 40:
            return "Extreme"
        elif spread > 25:
            return "High"
        elif spread > 15:
            return "Moderate"
        return "Low"

    def _classify_risk(self, probability: float) -> str:
        """Classify wildfire risk level."""
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

    def _get_contributing_factors(self, scores: Dict[str, float]) -> List[str]:
        """Get top contributing factors."""
        names = {
            "fuel_moisture": "dry_vegetation",
            "weather": "hot_dry_windy",
            "terrain": "steep_terrain",
            "fuel_type": "flammable_vegetation",
        }
        sorted_f = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [names[k] for k, v in sorted_f[:2] if v > 0.3]


_model_instance: Optional[FireModel] = None


def get_fire_model() -> FireModel:
    """Get or create singleton fire model."""
    global _model_instance
    if _model_instance is None:
        _model_instance = FireModel()
    return _model_instance
