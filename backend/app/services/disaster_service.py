"""Multi-hazard disaster risk assessment service.

Combines the landslide, flood, liquefaction and wildfire models into a
single assessment. Terrain, soil, vegetation and rainfall inputs are taken
from the shared site context so results reflect the actual location rather
than global defaults.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC
from typing import Any

from app.models.fire_model import get_fire_model
from app.models.flood_model import get_flood_model
from app.models.landslide_model import get_landslide_model
from app.models.liquefaction_model import get_liquefaction_model
from app.services.alert_service import get_alert_service
from app.services.cache_service import get_risk_cache
from app.services.soil_service import get_soil_service
from app.services.weather_service import get_weather_service

logger = logging.getLogger(__name__)


class DisasterService:
    """Service for multi-hazard disaster risk assessment."""

    def __init__(self) -> None:
        self._landslide = get_landslide_model()
        self._flood = get_flood_model()
        self._liquefaction = get_liquefaction_model()
        self._fire = get_fire_model()
        self._weather = get_weather_service()
        self._soil = get_soil_service()
        self._cache = get_risk_cache()

    async def assess_all_risks(
        self,
        latitude: float,
        longitude: float,
        elevation: float | None = None,
        slope: float | None = None,
        soil_type: str | None = None,
        sand_pct: float | None = None,
        clay_pct: float | None = None,
        land_cover: str = "cropland",
        ndvi: float | None = None,
        bulk_density: float | None = None,
    ) -> dict[str, Any]:
        """Perform a comprehensive multi-hazard risk assessment.

        Any omitted parameter is resolved from the shared site context
        (live weather, DEM-derived slope and ISRIC/analytical soil data).
        """
        cache_key = self._cache.make_key(
            "risk",
            lat=round(latitude, 3),
            lon=round(longitude, 3),
            lc=land_cover,
            elev=round(elevation, 1) if elevation is not None else None,
            slope=round(slope, 1) if slope is not None else None,
            soil=soil_type,
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        context = await self._soil.get_site_context(
            latitude, longitude, land_cover
        )

        elevation_value = (
            float(elevation) if elevation is not None else context["elevation_m"]
        )
        slope_value = (
            float(slope) if slope is not None else context["slope_degrees"]
        )
        ndvi_value = float(ndvi) if ndvi is not None else context["ndvi"]
        props = context["soil_properties"]
        texture = props.get("texture", {})

        soil_type_value = soil_type or texture.get("classification", "Loam")
        sand_value = (
            float(sand_pct) if sand_pct is not None else texture.get("sand_pct", 40.0)
        )
        clay_value = (
            float(clay_pct) if clay_pct is not None else texture.get("clay_pct", 25.0)
        )
        silt_value = max(0.0, 100.0 - sand_value - clay_value)
        bulk_density_value = (
            float(bulk_density)
            if bulk_density is not None
            else props.get("bulk_density_gcm3", 1.35)
        )

        weather = context["weather"]
        climate = context["climate"]
        soil_moisture = context["soil_moisture"]
        precipitation = context["precipitation"]

        temp = float(weather.get("temperature_c", 20.0))
        humidity = float(weather.get("humidity_pct", 50.0))
        wind = float(weather.get("wind_speed_kmh", 10.0))
        current_precip = float(weather.get("precipitation_mm", 0.0) or 0.0)
        soil_moisture_pct = float(soil_moisture.get("average_pct", 30.0))
        annual_precip = float(climate.get("mean_annual_precip_mm", 800.0))

        rainfall_24h = float(
            precipitation.get("last_24h_mm", current_precip) or current_precip
        )
        rainfall_7d = float(precipitation.get("last_7d_mm", rainfall_24h) or rainfall_24h)
        days_since_rain = int(precipitation.get("days_since_rain", 3) or 0)

        data_sources = list(context["data_sources"])
        data_warnings = list(context["data_warnings"])
        data_sources.append("open-meteo_precipitation" if precipitation.get("source") == "open-meteo" else "estimated_precipitation")

        # ---- Individual hazards ----
        landslide = self._landslide.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=elevation_value,
            slope=slope_value,
            soil_moisture=soil_moisture_pct,
            soil_type=soil_type_value,
            clay_pct=clay_value,
            rainfall_mm=rainfall_24h,
            ndvi=ndvi_value,
            land_cover=land_cover,
        )

        flood = self._flood.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=elevation_value,
            slope=slope_value,
            rainfall_mm_24h=rainfall_24h,
            rainfall_mm_annual=annual_precip,
            soil_type=soil_type_value,
            sand_pct=sand_value,
            clay_pct=clay_value,
            soil_moisture=soil_moisture_pct,
            land_cover=land_cover,
            ndvi=ndvi_value,
        )

        liquefaction = self._liquefaction.predict(
            sand_pct=sand_value,
            silt_pct=silt_value,
            clay_pct=clay_value,
            soil_type=soil_type_value,
            soil_moisture=soil_moisture_pct,
            bulk_density=bulk_density_value,
        )

        wildfire = self._fire.predict(
            latitude=latitude,
            longitude=longitude,
            temperature_c=temp,
            humidity_pct=humidity,
            wind_speed_kmh=wind,
            ndvi=ndvi_value,
            soil_moisture=soil_moisture_pct,
            rainfall_last_7d_mm=rainfall_7d,
            slope=slope_value,
            elevation=elevation_value,
            land_cover=land_cover,
            days_since_rain=days_since_rain,
        )

        composite = self._calculate_composite_risk(
            landslide["probability"],
            flood["probability"],
            liquefaction["probability_given_m7"],
            wildfire["probability"],
        )

        result = {
            "location": {
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "elevation_m": round(elevation_value, 1),
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
                    "vegetation_dryness_index": wildfire[
                        "vegetation_dryness_index"
                    ],
                },
            },
            "composite_risk_score": composite["score"],
            "composite_risk_level": composite["level"],
            "active_alerts": self._nearby_alerts(latitude, longitude),
            "current_conditions": {
                "temperature_c": temp,
                "humidity_pct": humidity,
                "wind_speed_kmh": wind,
                "precipitation_mm": current_precip,
                "rainfall_24h_mm": rainfall_24h,
                "rainfall_7d_mm": rainfall_7d,
                "soil_moisture_pct": soil_moisture_pct,
            },
            "site": {
                "land_cover": land_cover,
                "soil_type": soil_type_value,
                "slope_degrees": round(slope_value, 1),
                "ndvi": round(ndvi_value, 3),
            },
            "data_quality": {
                "sources": sorted(set(data_sources)),
                "warnings": data_warnings,
                "weather_source": weather.get("source", "unknown"),
                "climate_source": climate.get("source", "unknown"),
                "soil_moisture_source": soil_moisture.get("source", "unknown"),
                "precipitation_source": precipitation.get("source", "unknown"),
                "soil_data_source": (
                    "isric_soilgrids"
                    if context["isric_used"]
                    else "analytical_estimation"
                ),
                "is_fully_real_data": context["is_fully_real_data"],
                "_validation_status": "unvalidated_analytical_model",
                "note": (
                    "Risk models use analytical/heuristic methods, not trained "
                    "ML. Weights are expert-calibrated but not validated "
                    "against historical event inventories. Use as a screening "
                    "tool, not for engineering decisions."
                ),
            },
            "timestamp": self._timestamp(),
        }

        self._cache.set(cache_key, result)
        return result

    async def assess_landslide(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Assess landslide risk for a single location."""
        land_cover = kwargs.pop("land_cover", "cropland")
        context = await self._soil.get_site_context(
            latitude, longitude, land_cover
        )
        weather = context["weather"]
        precipitation = context["precipitation"]

        result = self._landslide.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=kwargs.pop("elevation", context["elevation_m"]),
            slope=kwargs.pop("slope", context["slope_degrees"]),
            soil_moisture=kwargs.pop(
                "soil_moisture", context["soil_moisture"].get("average_pct", 30)
            ),
            rainfall_mm=kwargs.pop(
                "rainfall_mm",
                precipitation.get(
                    "last_24h_mm", weather.get("precipitation_mm", 0)
                ),
            ),
            ndvi=kwargs.pop("ndvi", context["ndvi"]),
            **kwargs,
        )

        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "radius_km": radius_km,
            **result,
            "timestamp": self._timestamp(),
        }

    async def assess_flood(
        self, latitude: float, longitude: float, **kwargs: Any
    ) -> dict[str, Any]:
        """Assess flood risk for a single location."""
        land_cover = kwargs.pop("land_cover", "cropland")
        context = await self._soil.get_site_context(
            latitude, longitude, land_cover
        )
        weather = context["weather"]
        climate = context["climate"]
        precipitation = context["precipitation"]
        texture = context["soil_properties"].get("texture", {})

        result = self._flood.predict(
            latitude=latitude,
            longitude=longitude,
            elevation=kwargs.pop("elevation", context["elevation_m"]),
            slope=kwargs.pop("slope", context["slope_degrees"]),
            rainfall_mm_24h=kwargs.pop(
                "rainfall_mm_24h",
                precipitation.get(
                    "last_24h_mm", weather.get("precipitation_mm", 0)
                ),
            ),
            rainfall_mm_annual=kwargs.pop(
                "rainfall_mm_annual",
                climate.get("mean_annual_precip_mm", 800),
            ),
            soil_type=kwargs.pop(
                "soil_type", texture.get("classification", "Loam")
            ),
            sand_pct=kwargs.pop("sand_pct", texture.get("sand_pct", 40)),
            clay_pct=kwargs.pop("clay_pct", texture.get("clay_pct", 25)),
            soil_moisture=kwargs.pop(
                "soil_moisture", context["soil_moisture"].get("average_pct", 30)
            ),
            ndvi=kwargs.pop("ndvi", context["ndvi"]),
            **kwargs,
        )

        return {
            "location": {"latitude": latitude, "longitude": longitude},
            **result,
            "timestamp": self._timestamp(),
        }

    def _nearby_alerts(
        self, latitude: float, longitude: float, radius_km: float = 500.0
    ) -> list:
        """Return active alerts within ``radius_km`` of a location."""
        try:
            alerts = get_alert_service().get_active_alerts(limit=50)
        except Exception:  # pragma: no cover - alert service is in-memory
            return []

        nearby = []
        for alert in alerts:
            alert_lat = alert.get("latitude")
            alert_lon = alert.get("longitude")
            if alert_lat is None or alert_lon is None:
                continue
            distance = _haversine_km(
                latitude, longitude, float(alert_lat), float(alert_lon)
            )
            if distance <= radius_km:
                nearby.append({**alert, "distance_km": round(distance, 1)})
        return nearby[:10]

    def _calculate_composite_risk(
        self,
        landslide_prob: float,
        flood_prob: float,
        liquefaction_prob: float,
        wildfire_prob: float,
    ) -> dict[str, Any]:
        """Combine hazard probabilities into one 0-100 score.

        The score is 60 % worst hazard and 40 % weighted mean, so a single
        extreme hazard cannot be averaged away.
        """
        max_risk = max(
            landslide_prob, flood_prob, liquefaction_prob, wildfire_prob
        )
        weighted_mean = (
            landslide_prob * 0.30
            + flood_prob * 0.30
            + liquefaction_prob * 0.20
            + wildfire_prob * 0.20
        )
        composite = max_risk * 0.6 + weighted_mean * 0.4
        score = round(composite * 100)

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
        """Return the current UTC timestamp."""
        from datetime import datetime

        return datetime.now(UTC).isoformat()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


_service_instance: DisasterService | None = None


def get_disaster_service() -> DisasterService:
    """Return the singleton disaster service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = DisasterService()
    return _service_instance
