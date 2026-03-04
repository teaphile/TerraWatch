"""Weather data service.

Fetches weather data from Open-Meteo API (free, no key required)
and OpenWeatherMap API (requires API key).

Falls back to climate normals lookup when APIs are unavailable.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.cache_service import get_weather_cache

logger = logging.getLogger(__name__)
settings = get_settings()

OPEN_METEO_BASE = "https://api.open-meteo.com/v1"
OPEN_METEO_ELEVATION = "https://api.open-meteo.com/v1/elevation"

# Path to static data files
STATIC_DATA_DIR = Path(__file__).parent.parent / "data" / "static"

# Lazy-loaded climate normals and elevation grid
_climate_normals: Optional[Dict[str, Any]] = None
_elevation_grid: Optional[Dict[str, int]] = None


def _load_climate_normals() -> Dict[str, Any]:
    """Load climate normals lookup table (lazy, cached)."""
    global _climate_normals
    if _climate_normals is None:
        path = STATIC_DATA_DIR / "climate_normals.json"
        if path.exists():
            with open(path) as f:
                _climate_normals = json.load(f)
            logger.info(f"Loaded {len(_climate_normals)} climate normal grid points")
        else:
            logger.warning("climate_normals.json not found — using basic estimation")
            _climate_normals = {}
    return _climate_normals


def _load_elevation_grid() -> Dict[str, int]:
    """Load elevation grid lookup table (lazy, cached)."""
    global _elevation_grid
    if _elevation_grid is None:
        path = STATIC_DATA_DIR / "elevation_grid.json"
        if path.exists():
            with open(path) as f:
                _elevation_grid = json.load(f)
            logger.info(f"Loaded {len(_elevation_grid)} elevation grid points")
        else:
            logger.warning("elevation_grid.json not found — using basic estimation")
            _elevation_grid = {}
    return _elevation_grid


def _lookup_nearest_grid(lat: float, lon: float, grid: Dict[str, Any], resolution: int = 5) -> Optional[Any]:
    """Find the nearest grid point value using snapping."""
    snap_lat = round(lat / resolution) * resolution
    snap_lon = round(lon / resolution) * resolution
    key = f"{snap_lat},{snap_lon}"
    return grid.get(key)


def _interpolate_climate(lat: float, lon: float) -> Optional[Dict[str, float]]:
    """Interpolate climate normals from the nearest grid points.

    Uses inverse-distance weighting of up to 4 surrounding grid points.
    """
    normals = _load_climate_normals()
    if not normals:
        return None

    resolution = 5
    lat0 = int(math.floor(lat / resolution)) * resolution
    lat1 = lat0 + resolution
    lon0 = int(math.floor(lon / resolution)) * resolution
    lon1 = lon0 + resolution

    corners = [
        (lat0, lon0), (lat0, lon1),
        (lat1, lon0), (lat1, lon1),
    ]

    values = []
    weights = []
    for clat, clon in corners:
        key = f"{clat},{clon}"
        val = normals.get(key)
        if val is None:
            continue
        dist = math.sqrt((lat - clat) ** 2 + (lon - clon) ** 2)
        if dist < 0.01:
            return val  # Exact match
        w = 1.0 / dist
        values.append(val)
        weights.append(w)

    if not values:
        return None

    total_w = sum(weights)
    result = {}
    for k in values[0]:
        result[k] = round(sum(v[k] * w for v, w in zip(values, weights)) / total_w, 1)
    return result


class WeatherService:
    """Service for fetching weather and climate data.

    Uses Open-Meteo API as primary source (free, no API key).
    Falls back to climate normals lookup if API is unavailable.
    """

    def __init__(self) -> None:
        """Initialize weather service."""
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = get_weather_cache()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def get_current_weather(
        self, latitude: float, longitude: float
    ) -> Dict[str, Any]:
        """Get current weather conditions for a location."""
        cache_key = self._cache.make_key("weather", lat=round(latitude, 2), lon=round(longitude, 2))
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            if settings.OPEN_METEO_ENABLED:
                result = await self._fetch_open_meteo_current(latitude, longitude)
                self._cache.set(cache_key, result)
                return result
        except Exception as e:
            logger.warning(f"Weather API failed: {e}")

        return self._estimate_weather(latitude, longitude)

    async def get_climate_normals(
        self, latitude: float, longitude: float
    ) -> Dict[str, Any]:
        """Get climate normals (mean annual temperature and precipitation)."""
        cache_key = self._cache.make_key("climate", lat=round(latitude, 1), lon=round(longitude, 1))
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            if settings.OPEN_METEO_ENABLED:
                result = await self._fetch_climate_normals(latitude, longitude)
                self._cache.set(cache_key, result)
                return result
        except Exception as e:
            logger.warning(f"Climate API failed: {e}")

        return self._estimate_climate(latitude, longitude)

    async def get_soil_moisture(
        self, latitude: float, longitude: float
    ) -> Dict[str, Any]:
        """Get soil moisture data from Open-Meteo.

        Falls back to DB cache, then climate-based estimation.
        """
        cache_key = self._cache.make_key("soil_moisture", lat=round(latitude, 2), lon=round(longitude, 2))
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{OPEN_METEO_BASE}/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "hourly": "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm",
                    "forecast_days": 1,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                hourly = data.get("hourly", {})

                sm_0_1 = self._latest_value(hourly.get("soil_moisture_0_to_1cm", []))
                sm_1_3 = self._latest_value(hourly.get("soil_moisture_1_to_3cm", []))
                sm_3_9 = self._latest_value(hourly.get("soil_moisture_3_to_9cm", []))
                sm_9_27 = self._latest_value(hourly.get("soil_moisture_9_to_27cm", []))

                result = {
                    "surface_0_1cm": round(sm_0_1 * 100, 1) if sm_0_1 else None,
                    "shallow_1_3cm": round(sm_1_3 * 100, 1) if sm_1_3 else None,
                    "mid_3_9cm": round(sm_3_9 * 100, 1) if sm_3_9 else None,
                    "deep_9_27cm": round(sm_9_27 * 100, 1) if sm_9_27 else None,
                    "average_pct": round(
                        ((sm_0_1 or 0.3) + (sm_1_3 or 0.3) + (sm_3_9 or 0.3) + (sm_9_27 or 0.3)) / 4 * 100, 1
                    ),
                    "source": "open-meteo",
                }
                self._cache.set(cache_key, result)
                # Persist to DB cache for future fallback
                await self._persist_soil_moisture(latitude, longitude, result)
                return result
        except Exception as e:
            logger.warning(f"Soil moisture API failed: {e}")

        # Fallback 1: Check DB cache for recent nearby data
        db_cached = await self._get_cached_soil_moisture(latitude, longitude)
        if db_cached:
            return db_cached

        # Fallback 2: Estimate from climate normals
        return self._estimate_soil_moisture(latitude, longitude)

    async def get_elevation(
        self, latitude: float, longitude: float
    ) -> Dict[str, Any]:
        """Get elevation from Open-Meteo Elevation API.

        Falls back to static elevation grid if API fails.
        """
        cache_key = self._cache.make_key("elevation", lat=round(latitude, 3), lon=round(longitude, 3))
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                OPEN_METEO_ELEVATION,
                params={"latitude": latitude, "longitude": longitude},
            )
            if resp.status_code == 200:
                data = resp.json()
                elevations = data.get("elevation", [])
                if elevations and elevations[0] is not None:
                    result = {
                        "elevation_m": round(float(elevations[0]), 1),
                        "source": "open-meteo-elevation",
                    }
                    self._cache.set(cache_key, result)
                    return result
        except Exception as e:
            logger.warning(f"Elevation API failed: {e}")

        elev = self._lookup_elevation_grid(latitude, longitude)
        result = {
            "elevation_m": elev,
            "source": "elevation_grid_5deg",
            "_warning": "Elevation from low-resolution (5°) static grid. Open-Meteo Elevation API was unavailable.",
        }
        self._cache.set(cache_key, result)
        return result

    async def get_elevation_neighbors(
        self, latitude: float, longitude: float, delta: float = 0.01
    ) -> Dict[str, float]:
        """Get elevation for a point and its 4 cardinal neighbors.

        Used for slope computation from elevation gradient.
        """
        points = {
            "center": (latitude, longitude),
            "north": (latitude + delta, longitude),
            "south": (latitude - delta, longitude),
            "east": (latitude, longitude + delta),
            "west": (latitude, longitude - delta),
        }

        try:
            client = await self._get_client()
            lats = ",".join(str(p[0]) for p in points.values())
            lons = ",".join(str(p[1]) for p in points.values())
            resp = await client.get(
                OPEN_METEO_ELEVATION,
                params={"latitude": lats, "longitude": lons},
            )
            if resp.status_code == 200:
                data = resp.json()
                elevations = data.get("elevation", [])
                if len(elevations) == 5:
                    return {
                        name: round(float(elevations[i]), 1) if elevations[i] is not None else 0.0
                        for i, name in enumerate(points.keys())
                    }
        except Exception as e:
            logger.debug(f"Elevation neighbors API failed: {e}")

        return {
            name: self._lookup_elevation_grid(lat, lon)
            for name, (lat, lon) in points.items()
        }

    async def get_historical_data(
        self, latitude: float, longitude: float, days: int = 30,
    ) -> Dict[str, Any]:
        """Get historical weather data."""
        try:
            client = await self._get_client()
            end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

            resp = await client.get(
                f"{OPEN_METEO_BASE}/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum",
                    "start_date": start,
                    "end_date": end,
                    "timezone": "auto",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                return {
                    "dates": daily.get("time", []),
                    "temp_max": daily.get("temperature_2m_max", []),
                    "temp_min": daily.get("temperature_2m_min", []),
                    "precipitation": daily.get("precipitation_sum", []),
                    "rain": daily.get("rain_sum", []),
                    "source": "open-meteo",
                }
        except Exception as e:
            logger.warning(f"Historical weather API failed: {e}")

        return {"dates": [], "temp_max": [], "temp_min": [], "precipitation": [], "source": "unavailable"}

    # ---- Open-Meteo fetch helpers ----

    async def _fetch_open_meteo_current(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Fetch current weather from Open-Meteo API."""
        client = await self._get_client()
        resp = await client.get(
            f"{OPEN_METEO_BASE}/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,wind_direction_10m,weather_code",
                "forecast_days": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current", {})

        return {
            "temperature_c": current.get("temperature_2m", 20),
            "humidity_pct": current.get("relative_humidity_2m", 50),
            "precipitation_mm": current.get("precipitation", 0),
            "rain_mm": current.get("rain", 0),
            "wind_speed_kmh": current.get("wind_speed_10m", 10),
            "wind_direction_deg": current.get("wind_direction_10m", 0),
            "weather_code": current.get("weather_code", 0),
            "source": "open-meteo",
        }

    async def _fetch_climate_normals(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Fetch climate normals from Open-Meteo climate API."""
        client = await self._get_client()
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

        resp = await client.get(
            f"{OPEN_METEO_BASE}/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "start_date": start,
                "end_date": end,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})

        temps_max = [t for t in daily.get("temperature_2m_max", []) if t is not None]
        temps_min = [t for t in daily.get("temperature_2m_min", []) if t is not None]
        precip = [p for p in daily.get("precipitation_sum", []) if p is not None]

        mean_temp = sum(temps_max + temps_min) / max(len(temps_max + temps_min), 1)
        annual_precip = sum(precip) * (365 / max(len(precip), 1))

        return {
            "mean_annual_temp_c": round(mean_temp, 1),
            "mean_annual_precip_mm": round(annual_precip, 0),
            "source": "open-meteo",
        }

    # ---- Fallback estimation using climate normals ----

    def _estimate_weather(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Estimate weather from climate normals lookup.

        Uses a static climate normals dataset (5° resolution) instead
        of crude latitude-only formulas.
        """
        climate = _interpolate_climate(lat, lon)

        if climate:
            temp = climate["t"]
            humidity = climate["h"]
            precip_annual = climate["p"]
            wind = climate["w"]
            precip_daily = round(precip_annual / 365, 1)
        else:
            abs_lat = abs(lat)
            temp = round(27.0 - abs_lat * 0.55, 1)
            humidity = round(min(90, 50 + (90 - abs_lat) * 0.3), 1)
            precip_daily = 2.2
            wind = 12.0

        return {
            "temperature_c": round(temp, 1),
            "humidity_pct": round(min(95, max(10, humidity)), 1),
            "precipitation_mm": precip_daily,
            "rain_mm": precip_daily,
            "wind_speed_kmh": round(wind, 1),
            "wind_direction_deg": 180,
            "weather_code": 0,
            "source": "estimated",
            "_warning": (
                "Weather data is from climate normals (monthly/annual average at 5° resolution). "
                "Open-Meteo API was unavailable. Values are regional averages, "
                "not real-time observations."
            ),
        }

    def _estimate_climate(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Estimate climate normals from the static lookup table."""
        climate = _interpolate_climate(lat, lon)

        if climate:
            return {
                "mean_annual_temp_c": round(climate["t"], 1),
                "mean_annual_precip_mm": round(climate["p"]),
                "source": "climate_normals",
                "_warning": (
                    "Climate normals from static 5° resolution dataset. "
                    "Open-Meteo API was unavailable."
                ),
            }

        abs_lat = abs(lat)
        mean_temp = 27.0 - abs_lat * 0.55
        if abs_lat < 15:
            precip = 1800
        elif abs_lat < 30:
            precip = 500
        elif abs_lat < 50:
            precip = 900
        else:
            precip = 600

        return {
            "mean_annual_temp_c": round(mean_temp, 1),
            "mean_annual_precip_mm": precip,
            "source": "estimated",
            "_warning": (
                "Climate normals estimated from latitude-based heuristics. "
                "Both Open-Meteo API and climate normals file were unavailable."
            ),
        }

    def _estimate_soil_moisture(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Estimate soil moisture from climate normals.

        Wetter climates → higher moisture. Much better than
        returning identical values for all locations.
        """
        climate = _interpolate_climate(lat, lon)

        if climate:
            precip = climate["p"]
            temp = climate["t"]
            pet_proxy = max(temp * 5, 0)
            moisture_index = precip / max(precip + pet_proxy * 10, 1)
            base_moisture = moisture_index * 50 + 5
        else:
            abs_lat = abs(lat)
            if abs_lat < 15:
                base_moisture = 35
            elif abs_lat < 30:
                base_moisture = 15
            elif abs_lat < 50:
                base_moisture = 25
            else:
                base_moisture = 20

        surface = round(max(5, min(55, base_moisture * 0.85)), 1)
        shallow = round(max(8, min(58, base_moisture * 0.95)), 1)
        mid = round(max(10, min(60, base_moisture * 1.05)), 1)
        deep = round(max(12, min(60, base_moisture * 1.15)), 1)
        avg = round((surface + shallow + mid + deep) / 4, 1)

        return {
            "surface_0_1cm": surface,
            "shallow_1_3cm": shallow,
            "mid_3_9cm": mid,
            "deep_9_27cm": deep,
            "average_pct": avg,
            "source": "estimated_from_climate",
            "_warning": (
                "Soil moisture estimated from climate normals (annual precipitation "
                "and temperature). Open-Meteo soil moisture API was unavailable "
                "and no cached data was found."
            ),
        }

    # ---- Soil moisture DB cache ----

    async def _persist_soil_moisture(
        self, lat: float, lon: float, data: Dict[str, Any]
    ) -> None:
        """Persist soil moisture to DB for fallback use."""
        try:
            from app.database import async_session, SoilMoistureCache
            async with async_session() as session:
                record = SoilMoistureCache(
                    latitude=round(lat, 3),
                    longitude=round(lon, 3),
                    surface=data.get("surface_0_1cm", 0),
                    shallow=data.get("shallow_1_3cm", 0),
                    mid=data.get("mid_3_9cm", 0),
                    deep=data.get("deep_9_27cm", 0),
                    fetched_at=datetime.now(timezone.utc),
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist soil moisture cache: {e}")

    async def _get_cached_soil_moisture(
        self, lat: float, lon: float, max_age_hours: int = 24, radius: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """Look up recently cached soil moisture from DB."""
        try:
            from app.database import async_session, SoilMoistureCache
            from sqlalchemy import select

            cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            async with async_session() as session:
                stmt = (
                    select(SoilMoistureCache)
                    .where(
                        SoilMoistureCache.latitude.between(lat - radius, lat + radius),
                        SoilMoistureCache.longitude.between(lon - radius, lon + radius),
                        SoilMoistureCache.fetched_at >= cutoff,
                    )
                    .order_by(SoilMoistureCache.fetched_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    avg = round((row.surface + row.shallow + row.mid + row.deep) / 4, 1)
                    return {
                        "surface_0_1cm": row.surface,
                        "shallow_1_3cm": row.shallow,
                        "mid_3_9cm": row.mid,
                        "deep_9_27cm": row.deep,
                        "average_pct": avg,
                        "source": "cached",
                        "_warning": (
                            f"Soil moisture from DB cache (fetched {row.fetched_at.isoformat()}). "
                            "Open-Meteo API was unavailable."
                        ),
                    }
        except Exception as e:
            logger.debug(f"DB soil moisture cache lookup failed: {e}")
        return None

    # ---- Elevation helpers ----

    @staticmethod
    def _lookup_elevation_grid(lat: float, lon: float) -> float:
        """Look up elevation from the static 5° resolution grid."""
        grid = _load_elevation_grid()
        if grid:
            val = _lookup_nearest_grid(lat, lon, grid)
            if val is not None:
                return float(val)
        return 200.0

    @staticmethod
    def _latest_value(values: List) -> Optional[float]:
        """Get latest non-None value from a list."""
        for v in reversed(values):
            if v is not None:
                return v
        return None

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_service_instance: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Get or create singleton weather service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = WeatherService()
    return _service_instance
