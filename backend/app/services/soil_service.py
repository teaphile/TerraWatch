"""Soil analysis business logic.

Orchestrates soil property prediction, erosion calculation, carbon
sequestration estimation and health scoring. A single :meth:`get_site_context`
call gathers every environmental input concurrently so the soil and disaster
services share one consistent snapshot of a location.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import UTC
from typing import Any

from app.data.ingestion.soil_fetcher import get_soil_fetcher
from app.models.erosion_model import get_erosion_model
from app.models.soil_model import get_soil_model
from app.services.cache_service import get_soil_cache
from app.services.satellite_service import get_satellite_service
from app.services.weather_service import get_weather_service

logger = logging.getLogger(__name__)


class SoilService:
    """Service for comprehensive soil analysis."""

    def __init__(self) -> None:
        self._soil_model = get_soil_model()
        self._erosion_model = get_erosion_model()
        self._weather = get_weather_service()
        self._soil_fetcher = get_soil_fetcher()
        self._satellite = get_satellite_service()
        self._cache = get_soil_cache()

    # ------------------------------------------------------------------
    # Shared environmental context
    # ------------------------------------------------------------------

    async def get_site_context(
        self, latitude: float, longitude: float, land_cover: str = "cropland"
    ) -> dict[str, Any]:
        """Collect weather, terrain and soil data for a location.

        All upstream requests run concurrently and the result is cached, so
        calling this from both the soil and disaster endpoints does not
        trigger duplicate API traffic.
        """
        cache_key = self._cache.make_key(
            "site", lat=round(latitude, 3), lon=round(longitude, 3), lc=land_cover
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        results = await asyncio.gather(
            self._weather.get_current_weather(latitude, longitude),
            self._weather.get_climate_normals(latitude, longitude),
            self._weather.get_soil_moisture(latitude, longitude),
            self._weather.get_elevation(latitude, longitude),
            self._weather.get_elevation_neighbors(latitude, longitude),
            self._weather.get_precipitation_summary(latitude, longitude),
            self._soil_fetcher.fetch_properties(latitude, longitude),
            return_exceptions=True,
        )

        (
            weather_result,
            climate_result,
            moisture_result,
            elevation_result,
            neighbours_result,
            precipitation_result,
            isric_result,
        ) = results

        # ---- Resolve each result, falling back to estimates on failure ----
        weather = (
            weather_result
            if isinstance(weather_result, dict)
            else self._weather._estimate_weather(latitude, longitude)
        )
        climate = (
            climate_result
            if isinstance(climate_result, dict)
            else self._weather._estimate_climate(latitude, longitude)
        )
        soil_moisture_data = (
            moisture_result
            if isinstance(moisture_result, dict)
            else self._weather._estimate_soil_moisture(latitude, longitude)
        )
        precipitation = (
            precipitation_result
            if isinstance(precipitation_result, dict)
            else self._weather._estimate_precipitation(latitude, longitude)
        )
        isric_data = isric_result if isinstance(isric_result, dict) else None

        if isinstance(elevation_result, dict):
            elevation = float(elevation_result.get("elevation_m", 200.0))
            elevation_source = str(elevation_result.get("source", "estimated"))
        else:
            elevation = self._weather._lookup_elevation_grid(latitude, longitude)
            elevation_source = "etopo10_grid"

        if isinstance(neighbours_result, dict):
            neighbours = neighbours_result
        else:
            neighbours = {
                "center": elevation,
                "north": elevation,
                "south": elevation,
                "east": elevation,
                "west": elevation,
            }

        slope, slope_source = self._compute_slope(
            latitude, elevation, neighbours
        )
        mean_temp = float(climate.get("mean_annual_temp_c", 15.0))
        mean_precip = float(climate.get("mean_annual_precip_mm", 800.0))
        ndvi = float(
            self._satellite.estimate_ndvi(
                latitude, longitude, land_cover
            )["ndvi"]
        )

        data_sources: list[str] = []
        data_warnings: list[str] = []

        if isric_data:
            soil_props = self._isric_to_soil_props(isric_data)
            data_sources.append("isric_soilgrids")
        else:
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
            data_sources.append(
                soil_props.get("_data_source", "analytical_estimation")
            )
            data_warnings.append(
                "ISRIC SoilGrids API unavailable -- soil properties are "
                "estimated from analytical pedotransfer heuristics. Accuracy "
                "is significantly lower than observational data."
            )

        if climate.get("source") == "open-meteo":
            data_sources.append("open-meteo")
        else:
            data_sources.append("builtin_climatology")
            data_warnings.append(
                "Climate normals are estimated from the built-in climatology "
                "-- the Open-Meteo archive API was unavailable."
            )

        if weather.get("source") != "open-meteo":
            data_warnings.append(
                "Current weather is estimated from climate normals -- "
                "Open-Meteo was unavailable. Hazard scores may be less accurate."
            )

        if soil_moisture_data.get("source") == "open-meteo":
            data_sources.append("open-meteo_soil_moisture")
        elif soil_moisture_data.get("source") == "cached":
            data_warnings.append(
                "Soil moisture comes from a cached measurement rather than "
                "a live API reading."
            )
        else:
            data_warnings.append(
                "Soil moisture is estimated from climate normals, not "
                "measured by the Open-Meteo soil model."
            )

        # Use the measured / estimated profile average as the headline value.
        if soil_moisture_data.get("average_pct") is not None:
            is_live = soil_moisture_data.get("source") == "open-meteo"
            soil_props["moisture_pct"] = {
                "value": soil_moisture_data["average_pct"],
                "confidence": 0.90 if is_live else 0.60,
            }

        context = {
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "land_cover": land_cover,
            "weather": weather,
            "climate": climate,
            "soil_moisture": soil_moisture_data,
            "precipitation": precipitation,
            "elevation_m": round(elevation, 1),
            "elevation_source": elevation_source,
            "elevation_neighbors": neighbours,
            "slope_degrees": slope,
            "slope_source": slope_source,
            "ndvi": round(ndvi, 3),
            "soil_properties": soil_props,
            "isric_used": bool(isric_data),
            "data_sources": sorted(set(data_sources)),
            "data_warnings": data_warnings,
            "is_fully_real_data": bool(
                isric_data
                and climate.get("source") == "open-meteo"
                and weather.get("source") == "open-meteo"
                and soil_moisture_data.get("source") == "open-meteo"
            ),
        }

        self._cache.set(cache_key, context)
        return context

    # ------------------------------------------------------------------
    # Full analysis
    # ------------------------------------------------------------------

    async def analyze(
        self,
        latitude: float,
        longitude: float,
        elevation: float | None = None,
        land_cover: str = "cropland",
    ) -> dict[str, Any]:
        """Perform a complete soil analysis for a location."""
        cache_key = self._cache.make_key(
            "soil",
            lat=round(latitude, 3),
            lon=round(longitude, 3),
            lc=land_cover,
            elev=round(elevation, 1) if elevation is not None else None,
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        context = await self.get_site_context(latitude, longitude, land_cover)

        soil_props = dict(context["soil_properties"])

        if elevation is not None:
            # Honour a caller-supplied elevation: recompute the terrain
            # gradient around it and, when no observational soil data is
            # available, the elevation-dependent analytical soil prediction.
            elevation_value = float(elevation)
            elevation_source = "user_provided"
            slope, slope_source = self._compute_slope(
                latitude, elevation_value, context["elevation_neighbors"]
            )
            if not context["isric_used"]:
                soil_props = self._soil_model.predict(
                    latitude=latitude,
                    longitude=longitude,
                    elevation=elevation_value,
                    slope=slope,
                    mean_temp=float(
                        context["climate"].get("mean_annual_temp_c", 15.0)
                    ),
                    mean_precip=float(
                        context["climate"].get("mean_annual_precip_mm", 800.0)
                    ),
                    land_cover=land_cover,
                    ndvi=context["ndvi"],
                )
        else:
            elevation_value = context["elevation_m"]
            elevation_source = context["elevation_source"]
            slope = context["slope_degrees"]
            slope_source = context["slope_source"]
        climate = context["climate"]
        weather = context["weather"]
        soil_moisture_data = context["soil_moisture"]
        ndvi = context["ndvi"]
        mean_temp = float(climate.get("mean_annual_temp_c", 15.0))
        mean_precip = float(climate.get("mean_annual_precip_mm", 800.0))

        # RUSLE erosion
        slope_pct = math.tan(math.radians(slope)) * 100
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

        health = self._calculate_health_index(soil_props, erosion.risk_level)
        carbon = self._estimate_carbon_sequestration(
            soil_props["organic_carbon_pct"]["value"],
            soil_props["texture"]["clay_pct"],
            mean_temp,
            mean_precip,
            land_cover,
        )

        result = {
            "location": {
                **self._get_location_info(latitude, longitude, elevation_value),
                "elevation_m": round(elevation_value, 1),
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
                "elevation_source": elevation_source,
                "slope_source": slope_source,
            },
            "data_quality": {
                "sources": context["data_sources"],
                "warnings": context["data_warnings"],
                "soil_data_source": (
                    "isric_soilgrids"
                    if context["isric_used"]
                    else "analytical_estimation"
                ),
                "weather_data_source": climate.get("source", "unknown"),
                "soil_moisture_source": soil_moisture_data.get(
                    "source", "unknown"
                ),
                "is_fully_real_data": context["is_fully_real_data"],
            },
            "timestamp": self._timestamp(),
        }

        self._cache.set(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Scoring and estimates
    # ------------------------------------------------------------------

    def _calculate_health_index(
        self, props: dict[str, Any], erosion_risk: str
    ) -> dict[str, Any]:
        """Calculate the 0-100 soil health index."""

        def value_of(key: str, default: float) -> float:
            value = props.get(key, default)
            if isinstance(value, dict):
                value = value.get("value", default)
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        scores: list[float] = []

        ph = value_of("ph", 6.5)
        if 6.0 <= ph <= 7.0:
            ph_score = 100
        elif 5.5 <= ph <= 7.5:
            ph_score = 80
        elif 5.0 <= ph <= 8.0:
            ph_score = 60
        else:
            ph_score = 30
        scores.append(ph_score * 0.15)

        organic_carbon = value_of("organic_carbon_pct", 1.5)
        if organic_carbon >= 4.0:
            oc_score = 100
        elif organic_carbon >= 2.0:
            oc_score = 70
        elif organic_carbon >= 1.0:
            oc_score = 40
        else:
            oc_score = 20
        scores.append(oc_score * 0.25)

        sand = float(props["texture"]["sand_pct"])
        clay = float(props["texture"]["clay_pct"])
        if 20 <= sand <= 50 and 15 <= clay <= 35:
            texture_score = 90
        elif 10 <= sand <= 70 and 10 <= clay <= 45:
            texture_score = 65
        else:
            texture_score = 35
        scores.append(texture_score * 0.15)

        erosion_scores = {
            "Very Low": 100,
            "Low": 80,
            "Moderate": 55,
            "High": 30,
            "Very High": 15,
            "Severe": 5,
        }
        scores.append(erosion_scores.get(erosion_risk, 50) * 0.20)

        cec = value_of("cec_cmolkg", 15.0)
        if cec >= 25:
            cec_score = 100
        elif cec >= 15:
            cec_score = 75
        elif cec >= 10:
            cec_score = 50
        else:
            cec_score = 25
        scores.append(cec_score * 0.15)

        nitrogen = value_of("nitrogen_pct", 0.15)
        if nitrogen >= 0.3:
            n_score = 100
        elif nitrogen >= 0.15:
            n_score = 70
        elif nitrogen >= 0.08:
            n_score = 40
        else:
            n_score = 20
        scores.append(n_score * 0.10)

        total = round(min(100, max(0, sum(scores))), 0)

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
    ) -> dict[str, Any]:
        """Estimate soil organic-carbon stocks for the top 30 cm.

        Stock (t C/ha) = SOC% × bulk density (g/cm³) × depth (cm).
        """
        bulk_density = max(0.8, 1.4 - organic_carbon_pct * 0.05)
        depth_cm = 30.0

        current_stock = organic_carbon_pct * bulk_density * depth_cm

        clay_capacity = clay_pct * 0.5
        potential_oc = min(
            8.0, organic_carbon_pct * 1.5 + clay_capacity * 0.05
        )
        potential_bulk_density = max(0.8, bulk_density - 0.05)
        potential_stock = potential_oc * potential_bulk_density * depth_cm

        cover_factors = {
            "forest": 1.0,
            "grassland": 0.9,
            "cropland": 0.5,
            "shrubland": 0.8,
            "bare": 0.2,
        }
        management_factor = cover_factors.get(land_cover.lower(), 0.6)

        improvement = max(
            0.0,
            (potential_stock - current_stock) / max(current_stock, 1.0) * 100,
        )

        return {
            "current_stock_tons_ha": round(current_stock, 1),
            "potential_stock_tons_ha": round(potential_stock, 1),
            "improvement_potential_pct": round(improvement, 1),
            "management_factor": management_factor,
        }

    def _compute_slope(
        self,
        lat: float,
        center_elevation: float,
        neighbours: dict[str, float],
    ) -> tuple[float, str]:
        """Compute slope from a four-point elevation gradient."""
        elev_n = neighbours.get("north", center_elevation)
        elev_s = neighbours.get("south", center_elevation)
        elev_e = neighbours.get("east", center_elevation)
        elev_w = neighbours.get("west", center_elevation)

        if all(
            value == center_elevation
            for value in (elev_n, elev_s, elev_e, elev_w)
        ):
            return (
                self._estimate_slope_heuristic(center_elevation, lat),
                "estimated_heuristic",
            )

        dy = 2 * 0.01 * 111_111
        dx = 2 * 0.01 * 111_111 * max(math.cos(math.radians(lat)), 0.01)

        slope_ns = math.degrees(
            math.atan(abs(elev_n - elev_s) / max(dy, 1))
        )
        slope_ew = math.degrees(
            math.atan(abs(elev_e - elev_w) / max(dx, 1))
        )
        slope = math.sqrt(slope_ns**2 + slope_ew**2)
        return max(0.1, min(slope, 60.0)), "computed_from_dem"

    @staticmethod
    def _estimate_slope_heuristic(elevation: float, latitude: float) -> float:
        """Rough slope estimate used when no DEM gradient is available."""
        if elevation > 2000:
            return 25.0
        if elevation > 1000:
            return 15.0
        if elevation > 500:
            return 8.0
        if elevation > 200:
            return 5.0
        return 2.0

    def _isric_to_soil_props(self, isric_data: dict[str, Any]) -> dict[str, Any]:
        """Convert SoilGrids values to the internal soil property format."""
        model = self._soil_model

        raw_ph = isric_data.get("phh2o")
        ph = round(raw_ph / 10.0, 1) if raw_ph is not None else 6.5

        raw_soc = isric_data.get("soc")
        organic_carbon = round(raw_soc / 100.0, 2) if raw_soc is not None else 1.8

        raw_nitrogen = isric_data.get("nitrogen")
        nitrogen = (
            round(raw_nitrogen / 1000.0, 3) if raw_nitrogen is not None else 0.15
        )

        raw_sand = isric_data.get("sand")
        raw_silt = isric_data.get("silt")
        raw_clay = isric_data.get("clay")

        sand = round(raw_sand / 10.0, 1) if raw_sand is not None else 40.0
        silt = round(raw_silt / 10.0, 1) if raw_silt is not None else 35.0
        clay = round(raw_clay / 10.0, 1) if raw_clay is not None else 25.0

        total = sand + silt + clay
        if total > 0 and abs(total - 100.0) > 1.0:
            sand = round(sand / total * 100, 1)
            silt = round(silt / total * 100, 1)
            clay = round(100.0 - sand - silt, 1)

        texture_class = model._classify_texture(sand, silt, clay)

        raw_cec = isric_data.get("cec")
        cec = round(raw_cec / 10.0, 1) if raw_cec is not None else 15.0

        raw_bulk_density = isric_data.get("bdod")
        bulk_density = (
            round(raw_bulk_density / 100.0, 2)
            if raw_bulk_density is not None
            else 1.35
        )

        confidence = 0.80

        return {
            "ph": {
                "value": ph,
                "confidence": confidence,
                "category": model._ph_category(ph),
            },
            "organic_carbon_pct": {
                "value": organic_carbon,
                "confidence": confidence,
            },
            "nitrogen_pct": {
                "value": nitrogen,
                "confidence": confidence - 0.05,
            },
            "moisture_pct": {
                "value": 30.0,
                "confidence": 0.5,
            },
            "texture": {
                "sand_pct": sand,
                "silt_pct": silt,
                "clay_pct": clay,
                "classification": texture_class,
            },
            "bulk_density_gcm3": bulk_density,
            "cec_cmolkg": cec,
            "_data_source": "isric_soilgrids",
            "_source_detail": "ISRIC SoilGrids v2.0 -- 250 m global soil data",
        }

    @staticmethod
    def _get_location_info(
        lat: float, lon: float, elevation: float
    ) -> dict[str, Any]:
        """Return coarse location metadata."""
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
        """Return the current UTC timestamp as an ISO string."""
        from datetime import datetime

        return datetime.now(UTC).isoformat()


_service_instance: SoilService | None = None


def get_soil_service() -> SoilService:
    """Return the singleton soil service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SoilService()
    return _service_instance
