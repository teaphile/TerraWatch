"""Disaster risk assessment service.

Orchestrates landslide, flood, liquefaction, and wildfire
risk predictions into comprehensive risk reports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from app.models.landslide_model import get_landslide_model
from app.models.flood_model import get_flood_model
from app.models.liquefaction_model import get_liquefaction_model
from app.models.fire_model import get_fire_model
from app.services.cache_service import get_risk_cache
from app.services.weather_service import get_weather_service

logger = logging.getLogger(__name__)


class DisasterService:
    """Service for multi-hazard disaster risk assessment.

    Combines landslide, flood, liquefaction, and wildfire models
    into a composite risk analysis with real-time data integration.
    """

    def __init__(self) -> None:
        """Initialize disaster service with all risk models."""
        self._landslide = get_landslide_model()
        self._flood = get_flood_model()
        self._liquefaction = get_liquefaction_model()
        self._fire = get_fire_model()
        self._weather = get_weather_service()
        self._cache = get_risk_cache()

    async def assess_all_risks(
        self,
        latitude: float,
        longitude: float,
        elevation: float = 100.0,
        slope: float = 5.0,
        soil_type: str = "Loam",
        sand_pct: float = 40.0,
        clay_pct: float = 25.0,
        land_cover: str = "cropland",
        ndvi: float = 0.5,
    ) -> Dict[str, Any]:
        """Perform comprehensive multi-hazard risk assessment.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            elevation: Elevation in meters.
            slope: Slope angle in degrees.
            soil_type: USDA soil texture classification.
            sand_pct: Sand content percentage.
            clay_pct: Clay content percentage.
            land_cover: Land cover type.
            ndvi: Vegetation index (0-1).

        Returns:
            Comprehensive risk assessment with all hazard types.
        """
        cache_key = self._cache.make_key(
            "risk",
            lat=round(latitude, 3),
            lon=round(longitude, 3),
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        # Get current weather
        weather = await self._weather.get_current_weather(latitude, longitude)
        soil_moisture_data = await self._weather.get_soil_moisture(latitude, longitude)

        temp = weather.get("temperature_c", 20)
        humidity = weather.get("humidity_pct", 50)
        wind = weather.get("wind_speed_kmh", 10)
        precip = weather.get("precipitation_mm", 0) + weather.get("rain_mm", 0)
        soil_moisture = soil_moisture_data.get("average_pct", 30)

        climate = await self._weather.get_climate_normals(latitude, longitude)
        annual_precip = climate.get("mean_annual_precip_mm", 800)

        # Landslide risk
        landslide = self._landslide.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
            slope=slope,
            soil_moisture=soil_moisture,
            soil_type=soil_type,
            clay_pct=clay_pct,
            rainfall_mm=precip,
            ndvi=ndvi,
            land_cover=land_cover,
        )

        # Flood risk
        flood = self._flood.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
            slope=slope,
            rainfall_mm_24h=precip,
            rainfall_mm_annual=annual_precip,
            soil_type=soil_type,
            sand_pct=sand_pct,
            clay_pct=clay_pct,
            soil_moisture=soil_moisture,
            land_cover=land_cover,
            ndvi=ndvi,
        )

        # Liquefaction risk
        liquefaction = self._liquefaction.predict(
            sand_pct=sand_pct,
            silt_pct=100 - sand_pct - clay_pct,
            clay_pct=clay_pct,
            soil_type=soil_type,
            soil_moisture=soil_moisture,
        )

        # Wildfire risk
        wildfire = self._fire.predict(
            latitude=latitude,
            longitude=longitude,
            temperature_c=temp,
            humidity_pct=humidity,
            wind_speed_kmh=wind,
            ndvi=ndvi,
            soil_moisture=soil_moisture,
            slope=slope,
            elevation=elevation,
            land_cover=land_cover,
        )

        # Composite risk score
        composite = self._calculate_composite_risk(
            landslide["probability"],
            flood["probability"],
            liquefaction["susceptibility_score"],
            wildfire["probability"],
        )

        result = {
            "location": {
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
            },
            "risks": {
                "landslide": {
                    "probability": landslide["probability"],
                    "risk_level": landslide["risk_level"],
                    "contributing_factors": landslide["contributing_factors"],
                },
                "flood": {
                    "probability": flood["probability"],
                    "risk_level": flood["risk_level"],
                    "return_period_years": flood["return_period_years"],
                    "max_inundation_depth_m": flood["max_inundation_depth_m"],
                },
                "liquefaction": {
                    "susceptibility": liquefaction["susceptibility"],
                    "probability_given_m7": liquefaction["probability_given_m7"],
                    "soil_type_factor": liquefaction["soil_type_factor"],
                },
                "wildfire": {
                    "probability": wildfire["probability"],
                    "risk_level": wildfire["risk_level"],
                    "vegetation_dryness_index": wildfire["vegetation_dryness_index"],
                },
            },
            "composite_risk_score": composite["score"],
            "composite_risk_level": composite["level"],
            "active_alerts": [],
            "current_conditions": {
                "temperature_c": temp,
                "humidity_pct": humidity,
                "wind_speed_kmh": wind,
                "precipitation_mm": precip,
                "soil_moisture_pct": soil_moisture,
            },
            "timestamp": self._timestamp(),
        }

        self._cache.set(cache_key, result)
        return result

    async def assess_landslide(
        self, latitude: float, longitude: float, radius_km: float = 10.0, **kwargs: Any
    ) -> Dict[str, Any]:
        """Assess landslide risk specifically.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            radius_km: Analysis radius in km.
            **kwargs: Additional model parameters.

        Returns:
            Detailed landslide risk assessment.
        """
        weather = await self._weather.get_current_weather(latitude, longitude)
        soil_moisture = (await self._weather.get_soil_moisture(latitude, longitude)).get("average_pct", 30)

        result = self._landslide.predict(
            latitude=latitude,
            longitude=longitude,
            slope=kwargs.get("slope", 10),
            soil_moisture=soil_moisture,
            rainfall_mm=weather.get("precipitation_mm", 0),
            ndvi=kwargs.get("ndvi", 0.5),
            **{k: v for k, v in kwargs.items() if k not in ("slope", "ndvi")},
        )

        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "radius_km": radius_km,
            **result,
            "timestamp": self._timestamp(),
        }

    async def assess_flood(
        self, latitude: float, longitude: float, **kwargs: Any
    ) -> Dict[str, Any]:
        """Assess flood risk specifically."""
        weather = await self._weather.get_current_weather(latitude, longitude)
        climate = await self._weather.get_climate_normals(latitude, longitude)

        result = self._flood.predict(
            latitude=latitude,
            longitude=longitude,
            rainfall_mm_24h=weather.get("precipitation_mm", 0),
            rainfall_mm_annual=climate.get("mean_annual_precip_mm", 800),
            **kwargs,
        )

        return {
            "location": {"latitude": latitude, "longitude": longitude},
            **result,
            "timestamp": self._timestamp(),
        }

    def _calculate_composite_risk(
        self,
        landslide_prob: float,
        flood_prob: float,
        liquefaction_score: float,
        wildfire_prob: float,
    ) -> Dict[str, Any]:
        """Calculate composite risk from all hazard types.

        Uses maximum risk approach with weighted average.
        """
        max_risk = max(landslide_prob, flood_prob, liquefaction_score, wildfire_prob)
        avg_risk = (
            landslide_prob * 0.30 +
            flood_prob * 0.30 +
            liquefaction_score * 0.20 +
            wildfire_prob * 0.20
        )

        # Composite is 60% max risk + 40% average
        composite = max_risk * 0.6 + avg_risk * 0.4
        score = int(round(composite * 100))

        if score < 15:
            level = "Very Low"
        elif score < 30:
            level = "Low"
        elif score < 45:
            level = "Low-Moderate"
        elif score < 60:
            level = "Moderate"
        elif score < 75:
            level = "High"
        elif score < 90:
            level = "Very High"
        else:
            level = "Extreme"

        return {"score": score, "level": level}

    @staticmethod
    def _timestamp() -> str:
        """Get current UTC timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


_service_instance: Optional[DisasterService] = None


def get_disaster_service() -> DisasterService:
    """Get or create singleton disaster service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = DisasterService()
    return _service_instance
