"""Weather data service.

Fetches weather data from Open-Meteo API (free, no key required)
and OpenWeatherMap API (requires API key).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.cache_service import get_weather_cache

logger = logging.getLogger(__name__)
settings = get_settings()

OPEN_METEO_BASE = "https://api.open-meteo.com/v1"


class WeatherService:
    """Service for fetching weather and climate data.

    Uses Open-Meteo API as primary source (free, no API key).
    Falls back to analytical estimation if API is unavailable.
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
        """Get current weather conditions for a location.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.

        Returns:
            Dictionary with temperature, humidity, wind, precipitation, etc.
        """
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
        """Get climate normals (mean annual temperature and precipitation).

        Args:
            latitude: Location latitude.
            longitude: Location longitude.

        Returns:
            Dictionary with mean annual temperature and precipitation.
        """
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

        Args:
            latitude: Location latitude.
            longitude: Location longitude.

        Returns:
            Dictionary with soil moisture at various depths.
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

                # Get most recent values
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
                return result
        except Exception as e:
            logger.warning(f"Soil moisture API failed: {e}")

        return {
            "surface_0_1cm": 25.0,
            "shallow_1_3cm": 28.0,
            "mid_3_9cm": 30.0,
            "deep_9_27cm": 32.0,
            "average_pct": 28.8,
            "source": "estimated",
        }

    async def get_historical_data(
        self,
        latitude: float,
        longitude: float,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get historical weather data.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            days: Number of days of history.

        Returns:
            Dictionary with daily historical weather data.
        """
        try:
            client = await self._get_client()
            end = datetime.utcnow().strftime("%Y-%m-%d")
            start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

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
        # Use historical data to calculate normals
        end = datetime.utcnow().strftime("%Y-%m-%d")
        start = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")

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

    def _estimate_weather(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Estimate weather from latitude/longitude."""
        import math
        abs_lat = abs(lat)
        temp = 30 - abs_lat * 0.5
        humidity = 50 + (90 - abs_lat) * 0.3

        return {
            "temperature_c": round(temp, 1),
            "humidity_pct": round(min(90, humidity), 1),
            "precipitation_mm": 0,
            "rain_mm": 0,
            "wind_speed_kmh": 12,
            "wind_direction_deg": 180,
            "weather_code": 0,
            "source": "estimated",
        }

    def _estimate_climate(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """Estimate climate normals from latitude."""
        abs_lat = abs(lat)
        mean_temp = 30 - abs_lat * 0.55
        # Simple precipitation model: higher in tropics and mid-latitudes
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
        }

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
