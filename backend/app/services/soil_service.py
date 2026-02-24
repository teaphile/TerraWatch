"""Soil analysis business logic service.

Orchestrates soil property prediction, erosion calculation,
carbon sequestration estimation, and health scoring.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

from app.models.soil_model import get_soil_model
from app.models.erosion_model import get_erosion_model
from app.services.cache_service import get_soil_cache
from app.services.weather_service import get_weather_service

logger = logging.getLogger(__name__)


class SoilService:
    """Service for comprehensive soil analysis.

    Combines ML predictions, erosion modeling, carbon estimation,
    and health scoring into a complete soil analysis report.
    """

    def __init__(self) -> None:
        """Initialize soil analysis service."""
        self._soil_model = get_soil_model()
        self._erosion_model = get_erosion_model()
        self._weather = get_weather_service()
        self._cache = get_soil_cache()

    async def analyze(
        self,
        latitude: float,
        longitude: float,
        elevation: Optional[float] = None,
        land_cover: str = "cropland",
    ) -> Dict[str, Any]:
        """Perform comprehensive soil analysis for a location.

        Args:
            latitude: Location latitude (-90 to 90).
            longitude: Location longitude (-180 to 180).
            elevation: Elevation in meters (estimated if not provided).
            land_cover: Land cover type.

        Returns:
            Complete soil analysis report dictionary.
        """
        cache_key = self._cache.make_key(
            "soil",
            lat=round(latitude, 3),
            lon=round(longitude, 3),
            lc=land_cover,
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        # Get climate data
        climate = await self._weather.get_climate_normals(latitude, longitude)
        weather = await self._weather.get_current_weather(latitude, longitude)
        soil_moisture_data = await self._weather.get_soil_moisture(latitude, longitude)

        mean_temp = climate.get("mean_annual_temp_c", 15.0)
        mean_precip = climate.get("mean_annual_precip_mm", 800.0)

        if elevation is None:
            elevation = self._estimate_elevation(latitude, longitude)

        slope = self._estimate_slope(elevation, latitude)
        ndvi = self._estimate_ndvi(latitude, longitude, land_cover, mean_temp, mean_precip)

        # Predict soil properties
        soil_props = self._soil_model.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=elevation,
            slope=slope,
            mean_temp=mean_temp,
            mean_precip=mean_precip,
            land_cover=land_cover,
            ndvi=ndvi,
        )

        # Update moisture from actual data if available
        if soil_moisture_data.get("average_pct"):
            soil_props["moisture_pct"] = {
                "value": soil_moisture_data["average_pct"],
                "confidence": 0.90 if soil_moisture_data["source"] == "open-meteo" else 0.65,
            }

        # Calculate erosion risk
        slope_pct = np.tan(np.radians(slope)) * 100
        erosion = self._erosion_model.calculate(
            annual_precip_mm=mean_precip,
            sand_pct=soil_props["texture"]["sand_pct"],
            silt_pct=soil_props["texture"]["silt_pct"],
            clay_pct=soil_props["texture"]["clay_pct"],
            organic_carbon_pct=soil_props["organic_carbon_pct"]["value"],
            slope_pct=slope_pct,
            slope_length_m=100.0,
            land_cover=land_cover,
            ndvi=ndvi,
        )

        # Calculate health index
        health = self._calculate_health_index(soil_props, erosion.risk_level)

        # Carbon sequestration
        carbon = self._estimate_carbon_sequestration(
            soil_props["organic_carbon_pct"]["value"],
            soil_props["texture"]["clay_pct"],
            mean_temp,
            mean_precip,
            land_cover,
        )

        # Get location metadata
        location_info = self._get_location_info(latitude, longitude, elevation)

        result = {
            "location": {
                **location_info,
                "elevation_m": round(elevation, 1),
            },
            "soil_properties": soil_props,
            "soil_moisture": soil_moisture_data,
            "health_index": health,
            "erosion_risk": {
                "rusle_value_tons_ha_yr": erosion.soil_loss_tons_ha_yr,
                "risk_level": erosion.risk_level,
                "factors": {
                    "R": erosion.R,
                    "K": erosion.K,
                    "LS": erosion.LS,
                    "C": erosion.C,
                    "P": erosion.P,
                },
            },
            "carbon_sequestration": carbon,
            "climate": {
                "mean_annual_temp_c": mean_temp,
                "mean_annual_precip_mm": mean_precip,
                "current_weather": weather,
            },
            "metadata": {
                "ndvi": round(ndvi, 3),
                "slope_degrees": round(slope, 1),
                "land_cover": land_cover,
            },
            "timestamp": self._timestamp(),
        }

        self._cache.set(cache_key, result)
        return result

    def _calculate_health_index(
        self, props: Dict[str, Any], erosion_risk: str
    ) -> Dict[str, Any]:
        """Calculate overall soil health index (0-100).

        Considers pH, organic carbon, structure, erosion, and nutrient status.
        """
        scores = []

        # pH score (optimal: 6.0-7.0)
        ph = props["ph"]["value"]
        if 6.0 <= ph <= 7.0:
            ph_score = 100
        elif 5.5 <= ph <= 7.5:
            ph_score = 80
        elif 5.0 <= ph <= 8.0:
            ph_score = 60
        else:
            ph_score = 30
        scores.append(ph_score * 0.15)

        # Organic carbon score (higher = better)
        oc = props["organic_carbon_pct"]["value"]
        if oc >= 4.0:
            oc_score = 100
        elif oc >= 2.0:
            oc_score = 70
        elif oc >= 1.0:
            oc_score = 40
        else:
            oc_score = 20
        scores.append(oc_score * 0.25)

        # Texture balance (loam is ideal)
        sand = props["texture"]["sand_pct"]
        clay = props["texture"]["clay_pct"]
        if 20 <= sand <= 50 and 15 <= clay <= 35:
            text_score = 90
        elif 10 <= sand <= 70 and 10 <= clay <= 45:
            text_score = 65
        else:
            text_score = 35
        scores.append(text_score * 0.15)

        # Erosion score
        erosion_scores = {
            "Very Low": 100, "Low": 80, "Moderate": 55,
            "High": 30, "Very High": 15, "Severe": 5,
        }
        scores.append(erosion_scores.get(erosion_risk, 50) * 0.20)

        # CEC score (nutrient retention)
        cec = props.get("cec_cmolkg", 15)
        if cec >= 25:
            cec_score = 100
        elif cec >= 15:
            cec_score = 75
        elif cec >= 10:
            cec_score = 50
        else:
            cec_score = 25
        scores.append(cec_score * 0.15)

        # Nitrogen score
        n = props["nitrogen_pct"]["value"]
        if n >= 0.3:
            n_score = 100
        elif n >= 0.15:
            n_score = 70
        elif n >= 0.08:
            n_score = 40
        else:
            n_score = 20
        scores.append(n_score * 0.10)

        total = sum(scores)
        total = round(min(100, max(0, total)), 0)

        if total >= 85:
            grade, category = "A", "Excellent"
        elif total >= 70:
            grade, category = "B+", "Good"
        elif total >= 55:
            grade, category = "B", "Fair"
        elif total >= 40:
            grade, category = "C", "Poor"
        else:
            grade, category = "D", "Very Poor"

        return {
            "score": int(total),
            "grade": grade,
            "category": category,
        }

    def _estimate_carbon_sequestration(
        self,
        organic_carbon_pct: float,
        clay_pct: float,
        temp: float,
        precip: float,
        land_cover: str,
    ) -> Dict[str, Any]:
        """Estimate soil carbon stocks and sequestration potential."""
        # Current stock (tons/ha, top 30cm)
        # SOC stock = OC% * bulk_density * depth * 10
        bulk_density = 1.4 - organic_carbon_pct * 0.05
        current_stock = organic_carbon_pct * bulk_density * 30 * 0.1

        # Potential (based on climate and clay stabilization capacity)
        clay_capacity = clay_pct * 0.5  # clay stabilizes organic matter
        climate_factor = min(2.0, precip / 500) * max(0.3, 1 - temp / 40)
        potential_oc = min(8.0, organic_carbon_pct * 1.5 + clay_capacity * 0.05)
        potential_stock = potential_oc * (bulk_density - 0.05) * 30 * 0.1

        # Practice-based improvements
        cover_factors = {
            "forest": 1.0, "grassland": 0.9, "cropland": 0.5,
            "shrubland": 0.8, "bare": 0.2,
        }
        management_potential = cover_factors.get(land_cover.lower(), 0.6)

        improvement = max(0, (potential_stock - current_stock) / max(current_stock, 1) * 100)

        return {
            "current_stock_tons_ha": round(current_stock, 1),
            "potential_stock_tons_ha": round(potential_stock, 1),
            "improvement_potential_pct": round(improvement, 1),
            "management_factor": management_potential,
        }

    @staticmethod
    def _estimate_elevation(lat: float, lon: float) -> float:
        """Rough elevation estimate from coordinates."""
        import math
        abs_lat = abs(lat)
        # Very rough global elevation model
        base = 200
        if abs_lat > 60:
            base = 300
        if 25 < abs_lat < 45 and (70 < lon < 100 or -110 < lon < -100):
            base = 1500  # Mountain ranges
        if abs_lat < 10:
            base = 150  # Tropical lowlands
        return base + math.sin(lon * 0.1) * 100

    @staticmethod
    def _estimate_slope(elevation: float, latitude: float) -> float:
        """Estimate slope from elevation context."""
        if elevation > 2000:
            return 25.0
        elif elevation > 1000:
            return 15.0
        elif elevation > 500:
            return 8.0
        elif elevation > 200:
            return 5.0
        return 2.0

    @staticmethod
    def _estimate_ndvi(
        lat: float, lon: float, land_cover: str,
        temp: float, precip: float
    ) -> float:
        """Estimate NDVI from environmental variables."""
        cover_ndvi = {
            "forest": 0.7, "dense_forest": 0.8, "grassland": 0.5,
            "shrubland": 0.4, "cropland": 0.45, "bare": 0.1,
            "urban": 0.15, "water": 0.0, "wetland": 0.5,
        }
        base = cover_ndvi.get(land_cover.lower(), 0.4)

        # Climate adjustment
        if precip > 1000 and temp > 10:
            base *= 1.2
        elif precip < 300:
            base *= 0.6

        return float(np.clip(base, 0, 0.95))

    @staticmethod
    def _get_location_info(
        lat: float, lon: float, elevation: float
    ) -> Dict[str, Any]:
        """Get location metadata."""
        # Simple region classification
        if lat > 60:
            region = "Arctic/Subarctic"
        elif lat > 35:
            region = "Temperate"
        elif lat > 23.5:
            region = "Subtropical"
        elif lat > -23.5:
            region = "Tropical"
        elif lat > -35:
            region = "Subtropical (Southern)"
        else:
            region = "Temperate (Southern)"

        return {
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "region": region,
        }

    @staticmethod
    def _timestamp() -> str:
        """Get current UTC timestamp as ISO string."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


_service_instance: Optional[SoilService] = None


def get_soil_service() -> SoilService:
    """Get or create singleton soil service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SoilService()
    return _service_instance
