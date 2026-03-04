"""Soil analysis business logic service.

Orchestrates soil property prediction, erosion calculation,
carbon sequestration estimation, and health scoring.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from app.models.soil_model import get_soil_model
from app.models.erosion_model import get_erosion_model
from app.services.cache_service import get_soil_cache
from app.services.weather_service import get_weather_service
from app.data.ingestion.soil_fetcher import get_soil_fetcher

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
        self._soil_fetcher = get_soil_fetcher()
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

        # ---------- DATA SOURCE PRIORITY ----------
        # 1. Try ISRIC SoilGrids API (real observed/modeled data at 250m resolution)
        # 2. Fall back to analytical estimation (heuristic pedotransfer functions)
        data_sources: List[str] = []
        data_warnings: List[str] = []

        isric_data = await self._soil_fetcher.fetch_properties(latitude, longitude)
        if isric_data:
            soil_props = self._isric_to_soil_props(isric_data)
            data_sources.append("isric_soilgrids")
        else:
            data_warnings.append(
                "ISRIC SoilGrids API unavailable -- soil properties are estimated "
                "from analytical heuristics (latitude, climate, elevation). "
                "Accuracy is significantly lower than observational data."
            )
            # Predict soil properties using analytical model
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
            data_sources.append(soil_props.get("_data_source", "analytical_estimation"))

        # Track weather data source
        if climate.get("source") == "open-meteo":
            data_sources.append("open-meteo")
        else:
            data_sources.append("estimated_climate")
            data_warnings.append(
                "Climate normals estimated from latitude -- Open-Meteo API was unavailable."
            )

        if weather.get("source") == "estimated":
            data_warnings.append(
                "Current weather data estimated from latitude -- "
                "Open-Meteo API was unavailable. Risk scores may be less accurate."
            )

        if soil_moisture_data.get("source") == "estimated":
            data_warnings.append(
                "Soil moisture data is hardcoded fallback -- not from live API."
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
                "elevation_source": "estimated" if elevation == self._estimate_elevation(latitude, longitude) else "user_provided",
                "slope_source": "estimated",
            },
            "data_quality": {
                "sources": list(set(data_sources)),
                "warnings": data_warnings,
                "soil_data_source": "isric_soilgrids" if isric_data else "analytical_estimation",
                "weather_data_source": climate.get("source", "unknown"),
                "soil_moisture_source": soil_moisture_data.get("source", "unknown"),
                "is_fully_real_data": (
                    bool(isric_data)
                    and climate.get("source") == "open-meteo"
                    and soil_moisture_data.get("source") == "open-meteo"
                ),
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

        # Handle both ISRIC-based and analytical-based property formats
        def _get_value(prop_key: str, default: float = 0.0) -> float:
            val = props.get(prop_key, {})
            if isinstance(val, dict):
                return val.get("value", default)
            return float(val) if val is not None else default

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
        """Rough elevation estimate from coordinates.

        WARNING: This is a very crude heuristic -- not a real DEM lookup.
        A proper Digital Elevation Model (e.g. SRTM, ASTER GDEM) should
        be used for production/research use.
        """
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

    def _isric_to_soil_props(self, isric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ISRIC SoilGrids API response to internal soil property format.

        ISRIC SoilGrids returns values in specific units that need conversion:
        - phh2o: pH * 10 (e.g. 65 = pH 6.5)
        - soc: soil organic carbon in dg/kg (decigrams per kg)
        - nitrogen: total nitrogen in cg/kg (centigrams per kg)
        - sand, silt, clay: g/kg (grams per kg)
        - cec: CEC in mmol(c)/kg
        - bdod: bulk density in cg/cm³ (centigrams per cm³)
        """
        from app.models.soil_model import SoilPredictionModel

        model = SoilPredictionModel()

        # pH (SoilGrids: pH * 10)
        raw_ph = isric_data.get("phh2o")
        ph = round(raw_ph / 10.0, 1) if raw_ph is not None else 6.5

        # Organic carbon (SoilGrids: dg/kg → percentage: / 100)
        raw_soc = isric_data.get("soc")
        organic_carbon = round(raw_soc / 100.0, 2) if raw_soc is not None else 1.8

        # Nitrogen (SoilGrids: cg/kg → percentage: / 1000)
        raw_n = isric_data.get("nitrogen")
        nitrogen = round(raw_n / 1000.0, 3) if raw_n is not None else 0.15

        # Texture fractions (SoilGrids: g/kg → percentage: / 10)
        raw_sand = isric_data.get("sand")
        raw_silt = isric_data.get("silt")
        raw_clay = isric_data.get("clay")

        sand = round(raw_sand / 10.0, 1) if raw_sand is not None else 40.0
        silt = round(raw_silt / 10.0, 1) if raw_silt is not None else 35.0
        clay = round(raw_clay / 10.0, 1) if raw_clay is not None else 25.0

        # Normalize to 100%
        total = sand + silt + clay
        if total > 0 and abs(total - 100.0) > 1.0:
            sand = round(sand / total * 100, 1)
            silt = round(silt / total * 100, 1)
            clay = round(100.0 - sand - silt, 1)

        texture_class = model._classify_texture(sand, silt, clay)

        # CEC (SoilGrids: mmol(c)/kg → cmol(+)/kg: / 10)
        raw_cec = isric_data.get("cec")
        cec = round(raw_cec / 10.0, 1) if raw_cec is not None else 15.0

        # Bulk density (SoilGrids: cg/cm³ → g/cm³: / 100)
        raw_bdod = isric_data.get("bdod")
        bulk_density = round(raw_bdod / 100.0, 2) if raw_bdod is not None else 1.35

        # Confidence is higher for ISRIC data (peer-reviewed global model)
        confidence = 0.80

        return {
            "ph": {"value": ph, "confidence": confidence, "category": model._ph_category(ph)},
            "organic_carbon_pct": {"value": organic_carbon, "confidence": confidence},
            "nitrogen_pct": {"value": nitrogen, "confidence": confidence - 0.05},
            "moisture_pct": {"value": 30.0, "confidence": 0.5},  # ISRIC doesn't provide moisture; will be overridden
            "texture": {
                "sand_pct": sand,
                "silt_pct": silt,
                "clay_pct": clay,
                "classification": texture_class,
            },
            "bulk_density_gcm3": bulk_density,
            "cec_cmolkg": cec,
            "_data_source": "isric_soilgrids",
            "_source_detail": "ISRIC SoilGrids v2.0 -- 250m resolution global soil data",
        }

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
