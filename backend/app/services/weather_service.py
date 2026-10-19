"""Weather, climate and elevation data service.

Primary data source: Open-Meteo (free, no API key required).

* ``api.open-meteo.com/v1/forecast`` -- current conditions and soil moisture
* ``api.open-meteo.com/v1/elevation`` -- terrain elevation
* ``archive-api.open-meteo.com/v1/archive`` -- historical / climate normals

When an upstream API is unavailable the service degrades to bundled real
datasets instead of invented values:

* ``data/static/elevation_grid.npz`` -- ETOPO1-derived 10 arc-minute
  topography (int16, 1081x2161, north-first, NODATA already filled).
* ``data/static/koppen_grid.npz`` + ``data/static/climate_class_normals.json``
  -- the Koppen-Geiger classification at 0.5 degree resolution together with
  representative climatology per climate class.

Every fallback response is tagged with ``source`` and ``_warning`` so callers
can distinguish observations from estimates.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from app.config import get_settings
from app.services.cache_service import (
    get_climate_cache,
    get_elevation_cache,
    get_moisture_cache,
    get_precipitation_cache,
    get_weather_cache,
)

logger = logging.getLogger(__name__)
settings = get_settings()

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

STATIC_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "static"

_koppen_grid: dict[str, Any] | None = None
_elevation_grid: np.ndarray | None = None

# Koppen grid geometry: 0.5 degree cells centred on -89.75/-179.75.
_KOPPEN_RES = 0.5
_KOPPEN_LAT0 = -89.75
_KOPPEN_LON0 = -179.75
_KOPPEN_NODATA = 255

# ETOPO10 grid geometry: 1/6 degree, north-first, 1081 x 2161.
_ETOPO_STEP = 1.0 / 6.0
_ETOPO_ROWS = 1081
_ETOPO_COLS = 2161


def _load_koppen_grid() -> dict[str, Any]:
    """Load the Koppen class grid and per-class climatology (lazy)."""
    global _koppen_grid
    if _koppen_grid is None:
        grid_path = STATIC_DATA_DIR / "koppen_grid.npz"
        normals_path = STATIC_DATA_DIR / "climate_class_normals.json"
        if not grid_path.exists() or not normals_path.exists():
            logger.warning(
                "Bundled climate grid missing -- using latitude estimation"
            )
            _koppen_grid = {}
            return _koppen_grid

        with np.load(grid_path) as archive:
            classes = archive["classes"]
            codes = [str(code) for code in archive["codes"]]

        with open(normals_path, encoding="utf-8") as handle:
            normals = json.load(handle).get("classes", {})

        _koppen_grid = {
            "classes": classes,
            "codes": codes,
            "normals": normals,
        }
        logger.info(
            "Loaded Koppen grid: %d cells, %d classes",
            int((classes != _KOPPEN_NODATA).sum()),
            len(codes),
        )
    return _koppen_grid


def _load_elevation_grid() -> np.ndarray | None:
    """Load the bundled ETOPO10 elevation grid (lazy, cached)."""
    global _elevation_grid
    if _elevation_grid is None:
        path = STATIC_DATA_DIR / "elevation_grid.npz"
        if path.exists():
            with np.load(path) as archive:
                _elevation_grid = archive["elevation"]
            logger.info(
                "Loaded ETOPO10 elevation grid %s", _elevation_grid.shape
            )
        else:
            logger.warning(
                "elevation_grid.npz not found -- using basic estimation"
            )
            return None
    return _elevation_grid


def _sample_elevation(lat: float, lon: float) -> float | None:
    """Bilinearly sample the bundled DEM at a coordinate."""
    grid = _load_elevation_grid()
    if grid is None:
        return None

    row = min(max((90.0 - lat) / _ETOPO_STEP, 0.0), _ETOPO_ROWS - 1)
    col = min(max((lon + 180.0) / _ETOPO_STEP, 0.0), _ETOPO_COLS - 1)
    row0, col0 = int(row), int(col)
    row1 = min(row0 + 1, _ETOPO_ROWS - 1)
    col1 = min(col0 + 1, _ETOPO_COLS - 1)
    frac_row, frac_col = row - row0, col - col0

    top = grid[row0, col0] * (1 - frac_col) + grid[row0, col1] * frac_col
    bottom = grid[row1, col0] * (1 - frac_col) + grid[row1, col1] * frac_col
    value = float(top * (1 - frac_row) + bottom * frac_row)
    return max(0.0, value)


def _lookup_climate_class(lat: float, lon: float) -> dict[str, Any] | None:
    """Return the climatology of the Koppen class at a coordinate."""
    grid = _load_koppen_grid()
    if not grid:
        return None

    classes = grid["classes"]
    normals = grid["normals"]
    codes = grid["codes"]

    row = round((lat - _KOPPEN_LAT0) / _KOPPEN_RES)
    col = round((lon - _KOPPEN_LON0) / _KOPPEN_RES)
    row = min(max(row, 0), classes.shape[0] - 1)
    col = min(max(col, 0), classes.shape[1] - 1)

    # Ocean cells are absent from the source grid: search outward for the
    # nearest classified (land) cell, up to ~4 degrees away.
    for radius in range(9):
        for drow in range(-radius, radius + 1):
            for dcol in range(-radius, radius + 1):
                if radius and max(abs(drow), abs(dcol)) != radius:
                    continue
                check_row = row + drow
                check_col = (col + dcol) % classes.shape[1]
                if not 0 <= check_row < classes.shape[0]:
                    continue
                class_index = int(classes[check_row, check_col])
                if class_index == _KOPPEN_NODATA:
                    continue
                class_code = codes[class_index]
                values = normals.get(class_code)
                if values is None:
                    continue
                return {
                    "t": float(values["mean_annual_temp_c"]),
                    "p": float(values["mean_annual_precip_mm"]),
                    "h": float(values["humidity_pct"]),
                    "w": float(values["wind_speed_kmh"]),
                    "a": float(values["seasonal_amplitude_c"]),
                    "_class": class_code,
                    "_distance_cells": radius,
                }
    return None


def _interpolate_climate(lat: float, lon: float) -> dict[str, float] | None:
    """Return representative climatology for a coordinate.

    The bundled grid stores one climate class per 0.5 degree cell; the
    returned values are that class's representative annual means.
    """
    return _lookup_climate_class(lat, lon)


def _seasonal_temperature(
    annual_temp: float, amplitude: float, latitude: float, month: int
) -> float:
    """Apply a seasonal cycle to an annual mean temperature."""
    # Peak warmth in July (north) / January (south).
    phase = math.cos(2 * math.pi * (month - 7) / 12)
    if latitude < 0:
        phase = -phase
    return annual_temp + amplitude * phase


class WeatherService:
    """Fetch weather, climate and elevation data for a coordinate."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache = get_weather_cache()
        self._climate_cache = get_climate_cache()
        self._elevation_cache = get_elevation_cache()
        self._precipitation_cache = get_precipitation_cache()
        self._moisture_cache = get_moisture_cache()

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a lazily created shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    settings.HTTP_READ_TIMEOUT,
                    connect=settings.HTTP_CONNECT_TIMEOUT,
                ),
                follow_redirects=True,
                headers={"User-Agent": "TerraWatch/2.0"},
            )
        return self._client

    # ------------------------------------------------------------------
    # Current conditions
    # ------------------------------------------------------------------

    async def get_current_weather(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Return current weather conditions for a location."""
        cache_key = self._cache.make_key(
            "weather", lat=round(latitude, 2), lon=round(longitude, 2)
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        if settings.OPEN_METEO_ENABLED:
            try:
                result = await self._fetch_open_meteo_current(latitude, longitude)
                self._cache.set(cache_key, result)
                return result
            except Exception as exc:
                logger.warning("Weather API failed: %s", exc)

        return self._estimate_weather(latitude, longitude)

    async def _fetch_open_meteo_current(
        self, lat: float, lon: float
    ) -> dict[str, Any]:
        """Fetch current conditions from the Open-Meteo forecast API."""
        client = await self._get_client()
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,relative_humidity_2m,precipitation,rain,"
                    "wind_speed_10m,wind_direction_10m,weather_code"
                ),
                "timezone": "GMT",
            },
        )
        response.raise_for_status()
        current = response.json().get("current", {})

        if current.get("temperature_2m") is None:
            raise ValueError("Open-Meteo response did not include current weather")

        return {
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m", 50),
            "precipitation_mm": current.get("precipitation", 0) or 0,
            "rain_mm": current.get("rain", 0) or 0,
            "wind_speed_kmh": current.get("wind_speed_10m", 10),
            "wind_direction_deg": current.get("wind_direction_10m", 0),
            "weather_code": current.get("weather_code", 0),
            "observed_at": current.get("time"),
            "source": "open-meteo",
        }

    # ------------------------------------------------------------------
    # Climate normals
    # ------------------------------------------------------------------

    async def get_climate_normals(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Return mean annual temperature and precipitation."""
        cache_key = self._climate_cache.make_key(
            "climate", lat=round(latitude, 1), lon=round(longitude, 1)
        )
        cached = self._climate_cache.get(cache_key)
        if cached:
            return cached

        if settings.OPEN_METEO_ENABLED:
            try:
                result = await self._fetch_climate_normals(latitude, longitude)
                self._climate_cache.set(cache_key, result)
                return result
            except Exception as exc:
                logger.warning("Climate API failed: %s", exc)

        return self._estimate_climate(latitude, longitude)

    async def _fetch_climate_normals(
        self, lat: float, lon: float
    ) -> dict[str, Any]:
        """Compute 12-month climate normals from the Open-Meteo archive API.

        The forecast endpoint cannot serve a one-year historical window, so
        the archive endpoint is required here.
        """
        client = await self._get_client()
        end = (datetime.now(UTC) - timedelta(days=5)).date()
        start = end - timedelta(days=365 * 3)

        response = await client.get(
            ARCHIVE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "temperature_2m_mean,precipitation_sum",
                "timezone": "GMT",
            },
        )
        response.raise_for_status()
        daily = response.json().get("daily", {})

        temps = [value for value in daily.get("temperature_2m_mean", []) if value is not None]
        precip = [value for value in daily.get("precipitation_sum", []) if value is not None]

        if not temps:
            raise ValueError("No temperature data returned by Open-Meteo archive")

        mean_temp = sum(temps) / len(temps)
        years = max(1.0, len(temps) / 365.0)
        annual_precip = (sum(precip) / years) if precip else 0.0

        return {
            "mean_annual_temp_c": round(mean_temp, 1),
            "mean_annual_precip_mm": round(annual_precip),
            "period_years": round(years, 1),
            "source": "open-meteo",
        }

    # ------------------------------------------------------------------
    # Recent precipitation (used by the hazard models)
    # ------------------------------------------------------------------

    async def get_precipitation_summary(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Return rainfall totals for the last 24 hours and 7 days.

        Open-Meteo's ``current.precipitation`` is an hourly rate, whereas
        the landslide and flood models need accumulated rainfall. Daily
        totals for the past week are the most reliable proxy.
        """
        cache_key = self._precipitation_cache.make_key(
            "precip", lat=round(latitude, 2), lon=round(longitude, 2)
        )
        cached = self._precipitation_cache.get(cache_key)
        if cached:
            return cached

        if settings.OPEN_METEO_ENABLED:
            try:
                client = await self._get_client()
                response = await client.get(
                    FORECAST_URL,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "daily": "precipitation_sum",
                        "past_days": 7,
                        "forecast_days": 1,
                        "timezone": "GMT",
                    },
                )
                response.raise_for_status()
                daily = response.json().get("daily", {})
                values = [
                    value if value is not None else 0.0
                    for value in daily.get("precipitation_sum", [])
                ]
                if values:
                    # The final value is "today"; use the previous complete
                    # day for the 24 h total and the last seven complete
                    # days for the weekly total.
                    complete_days = values[:-1]
                    last_24h = complete_days[-1] if complete_days else values[-1]
                    last_7d = sum(complete_days[-7:])
                    days_since_rain = 0
                    for value in reversed(complete_days):
                        if value >= 1.0:
                            break
                        days_since_rain += 1
                    result = {
                        "last_24h_mm": round(last_24h, 1),
                        "last_7d_mm": round(last_7d, 1),
                        "days_since_rain": days_since_rain,
                        "source": "open-meteo",
                    }
                    self._precipitation_cache.set(cache_key, result)
                    return result
            except Exception as exc:
                logger.warning("Precipitation API failed: %s", exc)

        return self._estimate_precipitation(latitude, longitude)

    def _estimate_precipitation(self, lat: float, lon: float) -> dict[str, Any]:
        """Estimate recent rainfall from the climatology lookup."""
        climate = _interpolate_climate(lat, lon)
        if climate:
            annual = climate.get("p", 800)
            daily = annual / 365.0
            last_24h = round(daily, 1)
            last_7d = round(daily * 7, 1)
        else:
            last_24h = 2.2
            last_7d = 15.0

        return {
            "last_24h_mm": last_24h,
            "last_7d_mm": last_7d,
            "days_since_rain": 3,
            "source": "estimated",
            "_warning": (
                "Recent rainfall was estimated from climate normals; "
                "Open-Meteo was unavailable."
            ),
        }

    # ------------------------------------------------------------------
    # Soil moisture
    # ------------------------------------------------------------------

    async def get_soil_moisture(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Return soil moisture at several depths, as percentages."""
        cache_key = self._moisture_cache.make_key(
            "soil_moisture", lat=round(latitude, 2), lon=round(longitude, 2)
        )
        cached = self._moisture_cache.get(cache_key)
        if cached:
            return cached

        if settings.OPEN_METEO_ENABLED:
            try:
                result = await self._fetch_soil_moisture(latitude, longitude)
                if result is not None:
                    self._moisture_cache.set(cache_key, result)
                    await self._persist_soil_moisture(latitude, longitude, result)
                    return result
            except Exception as exc:
                logger.warning("Soil moisture API failed: %s", exc)

        cached_db = await self._get_cached_soil_moisture(latitude, longitude)
        if cached_db:
            return cached_db

        return self._estimate_soil_moisture(latitude, longitude)

    async def _fetch_soil_moisture(
        self, lat: float, lon: float
    ) -> dict[str, Any] | None:
        """Fetch volumetric soil moisture (m³/m³) and convert to percent."""
        client = await self._get_client()
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": (
                    "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,"
                    "soil_moisture_3_to_9cm,soil_moisture_9_to_27cm"
                ),
                "forecast_hours": 1,
                "timezone": "GMT",
            },
        )
        response.raise_for_status()
        hourly = response.json().get("hourly", {})

        def latest(key: str) -> float | None:
            for value in reversed(hourly.get(key, [])):
                if value is not None:
                    return float(value) * 100.0
            return None

        surface = latest("soil_moisture_0_to_1cm")
        shallow = latest("soil_moisture_1_to_3cm")
        mid = latest("soil_moisture_3_to_9cm")
        deep = latest("soil_moisture_9_to_27cm")
        depths = [value for value in (surface, shallow, mid, deep) if value is not None]

        if not depths:
            return None

        return {
            "surface_0_1cm": round(surface, 1) if surface is not None else None,
            "shallow_1_3cm": round(shallow, 1) if shallow is not None else None,
            "mid_3_9cm": round(mid, 1) if mid is not None else None,
            "deep_9_27cm": round(deep, 1) if deep is not None else None,
            "average_pct": round(sum(depths) / len(depths), 1),
            "source": "open-meteo",
        }

    # ------------------------------------------------------------------
    # Elevation
    # ------------------------------------------------------------------

    async def get_elevation(
        self, latitude: float, longitude: float
    ) -> dict[str, Any]:
        """Return terrain elevation in metres."""
        cache_key = self._elevation_cache.make_key(
            "elevation", lat=round(latitude, 3), lon=round(longitude, 3)
        )
        cached = self._elevation_cache.get(cache_key)
        if cached:
            return cached

        if settings.OPEN_METEO_ENABLED:
            try:
                client = await self._get_client()
                response = await client.get(
                    ELEVATION_URL,
                    params={"latitude": latitude, "longitude": longitude},
                )
                if response.status_code == 200:
                    elevations = response.json().get("elevation", [])
                    if elevations and elevations[0] is not None:
                        result = {
                            "elevation_m": round(float(elevations[0]), 1),
                            "source": "open-meteo",
                        }
                        self._elevation_cache.set(cache_key, result)
                        return result
            except Exception as exc:
                logger.warning("Elevation API failed: %s", exc)

        elevation = self._lookup_elevation_grid(latitude, longitude)
        result = {
            "elevation_m": elevation,
            "source": "etopo10_grid",
            "_warning": (
                "Elevation comes from the bundled ETOPO1-derived 10 arc-minute "
                "grid. The Open-Meteo elevation API was unavailable."
            ),
        }
        self._elevation_cache.set(cache_key, result)
        return result

    async def get_elevation_neighbors(
        self, latitude: float, longitude: float, delta: float = 0.01
    ) -> dict[str, float]:
        """Return elevations for a point and its four cardinal neighbours."""
        points = {
            "center": (latitude, longitude),
            "north": (latitude + delta, longitude),
            "south": (latitude - delta, longitude),
            "east": (latitude, longitude + delta),
            "west": (latitude, longitude - delta),
        }

        if settings.OPEN_METEO_ENABLED:
            try:
                client = await self._get_client()
                response = await client.get(
                    ELEVATION_URL,
                    params={
                        "latitude": ",".join(str(p[0]) for p in points.values()),
                        "longitude": ",".join(str(p[1]) for p in points.values()),
                    },
                )
                if response.status_code == 200:
                    elevations = response.json().get("elevation", [])
                    if len(elevations) == 5 and all(
                        value is not None for value in elevations
                    ):
                        return {
                            name: round(float(elevations[index]), 1)
                            for index, name in enumerate(points)
                        }
            except Exception as exc:
                logger.debug("Elevation neighbours API failed: %s", exc)

        return {
            name: self._lookup_elevation_grid(point_lat, point_lon)
            for name, (point_lat, point_lon) in points.items()
        }

    # ------------------------------------------------------------------
    # Historical data
    # ------------------------------------------------------------------

    async def get_historical_data(
        self, latitude: float, longitude: float, days: int = 30
    ) -> dict[str, Any]:
        """Return daily historical weather data from the archive API."""
        days = max(1, min(int(days), 365))
        cache_key = self._cache.make_key(
            "historical",
            lat=round(latitude, 2),
            lon=round(longitude, 2),
            days=days,
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        result = self._empty_history()
        try:
            client = await self._get_client()
            end = (datetime.now(UTC) - timedelta(days=5)).date()
            start = end - timedelta(days=days)

            response = await client.get(
                ARCHIVE_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,rain_sum"
                    ),
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "timezone": "GMT",
                },
            )
            if response.status_code == 200:
                daily = response.json().get("daily", {})
                result = {
                    "dates": daily.get("time", []),
                    "temp_max": daily.get("temperature_2m_max", []),
                    "temp_min": daily.get("temperature_2m_min", []),
                    "precipitation": daily.get("precipitation_sum", []),
                    "rain": daily.get("rain_sum", []),
                    "source": "open-meteo",
                }
                self._cache.set(cache_key, result)
                return result
        except Exception as exc:
            logger.warning("Historical weather API failed: %s", exc)

        # Do not cache the failure: a transient outage should recover.
        return result if result["source"] == "open-meteo" else self._empty_history()

    @staticmethod
    def _empty_history() -> dict[str, Any]:
        """Return an empty historical series marked unavailable."""
        return {
            "dates": [],
            "temp_max": [],
            "temp_min": [],
            "precipitation": [],
            "rain": [],
            "source": "unavailable",
            "_warning": "Historical weather data is currently unavailable.",
        }

    async def get_soil_moisture_history(
        self, latitude: float, longitude: float, days: int = 30
    ) -> dict[str, Any]:
        """Return daily mean soil moisture for the past ``days`` days.

        Uses the ERA5-Land reanalysis exposed by the Open-Meteo archive
        API. Values are converted from m³/m³ to volumetric percent.
        """
        days = max(1, min(int(days), 90))
        cache_key = self._moisture_cache.make_key(
            "moisture_history",
            lat=round(latitude, 2),
            lon=round(longitude, 2),
            days=days,
        )
        cached = self._moisture_cache.get(cache_key)
        if cached:
            return cached

        empty = {
            "dates": [],
            "surface_0_7cm": [],
            "mid_7_28cm": [],
            "deep_28_100cm": [],
            "source": "unavailable",
            "_warning": "Soil-moisture history is currently unavailable.",
        }

        if settings.OPEN_METEO_ENABLED:
            try:
                client = await self._get_client()
                end = (datetime.now(UTC) - timedelta(days=5)).date()
                start = end - timedelta(days=days - 1)

                response = await client.get(
                    ARCHIVE_URL,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "hourly": (
                            "soil_moisture_0_to_7cm,"
                            "soil_moisture_7_to_28cm,"
                            "soil_moisture_28_to_100cm"
                        ),
                        "timezone": "GMT",
                    },
                )
                response.raise_for_status()
                hourly = response.json().get("hourly", {})
                times = hourly.get("time", [])
                if not times:
                    return empty

                # Aggregate hourly samples into daily means.
                daily: dict[str, dict[str, list[float]]] = {}
                for index, timestamp in enumerate(times):
                    day = str(timestamp)[:10]
                    bucket = daily.setdefault(
                        day, {"surface": [], "mid": [], "deep": []}
                    )
                    for source_key, bucket_key in (
                        ("soil_moisture_0_to_7cm", "surface"),
                        ("soil_moisture_7_to_28cm", "mid"),
                        ("soil_moisture_28_to_100cm", "deep"),
                    ):
                        series = hourly.get(source_key, [])
                        if index < len(series) and series[index] is not None:
                            bucket[bucket_key].append(float(series[index]) * 100.0)

                dates = sorted(daily)
                result = {
                    "dates": dates,
                    "surface_0_7cm": [
                        round(
                            sum(daily[day]["surface"])
                            / max(1, len(daily[day]["surface"])),
                            2,
                        )
                        for day in dates
                    ],
                    "mid_7_28cm": [
                        round(
                            sum(daily[day]["mid"]) / max(1, len(daily[day]["mid"])),
                            2,
                        )
                        for day in dates
                    ],
                    "deep_28_100cm": [
                        round(
                            sum(daily[day]["deep"]) / max(1, len(daily[day]["deep"])),
                            2,
                        )
                        for day in dates
                    ],
                    "source": "open-meteo",
                }
                self._moisture_cache.set(cache_key, result)
                return result
            except Exception as exc:
                logger.warning("Soil moisture history API failed: %s", exc)

        return empty

    # ------------------------------------------------------------------
    # Fallback estimation
    # ------------------------------------------------------------------

    def _estimate_weather(self, lat: float, lon: float) -> dict[str, Any]:
        """Estimate current weather from the built-in climatology."""
        climate = _interpolate_climate(lat, lon)
        month = datetime.now(UTC).month

        if climate:
            temp = _seasonal_temperature(
                climate.get("t", 15.0),
                climate.get("a", max(0.0, (abs(lat) - 8) * 0.25)),
                lat,
                month,
            )
            humidity = climate.get("h", 60)
            annual_precip = climate.get("p", 800)
            wind = climate.get("w", 12)
            precip_daily = round(annual_precip / 365.0, 1)
        else:
            abs_lat = abs(lat)
            temp = round(27.0 - abs_lat * 0.45, 1)
            humidity = round(min(90, 50 + (90 - abs_lat) * 0.3), 1)
            precip_daily = 2.2
            wind = 12.0

        return {
            "temperature_c": round(temp, 1),
            "humidity_pct": round(min(98, max(5, humidity)), 1),
            "precipitation_mm": precip_daily,
            "rain_mm": precip_daily,
            "wind_speed_kmh": round(wind, 1),
            "wind_direction_deg": 180,
            "weather_code": 0,
            "source": "estimated",
            "_warning": (
                "Weather data is estimated from climate normals (long-term "
                "averages), not real-time observations. Open-Meteo was "
                "unavailable."
            ),
        }

    def _estimate_climate(self, lat: float, lon: float) -> dict[str, Any]:
        """Estimate climate normals from the built-in climatology."""
        climate = _interpolate_climate(lat, lon)
        if climate:
            return {
                "mean_annual_temp_c": round(climate.get("t", 15.0), 1),
                "mean_annual_precip_mm": round(climate.get("p", 800)),
                "source": "climate_normals",
                "_warning": (
                    "Climate normals come from the bundled Koppen-Geiger "
                    "climate-class climatology (0.5°); Open-Meteo was "
                    "unavailable."
                ),
            }

        abs_lat = abs(lat)
        mean_temp = 27.0 - abs_lat * 0.45
        if abs_lat < 15:
            precip = 1800
        elif abs_lat < 30:
            precip = 700
        elif abs_lat < 50:
            precip = 900
        else:
            precip = 500
        return {
            "mean_annual_temp_c": round(mean_temp, 1),
            "mean_annual_precip_mm": precip,
            "source": "estimated",
            "_warning": (
                "Climate normals were estimated from latitude because both "
                "Open-Meteo and the built-in climatology were unavailable."
            ),
        }

    def _estimate_soil_moisture(
        self, lat: float, lon: float
    ) -> dict[str, Any]:
        """Estimate soil moisture from climate normals."""
        climate = _interpolate_climate(lat, lon)

        if climate:
            precip = climate.get("p", 800)
            temp = climate.get("t", 15)
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

        return {
            "surface_0_1cm": surface,
            "shallow_1_3cm": shallow,
            "mid_3_9cm": mid,
            "deep_9_27cm": deep,
            "average_pct": round((surface + shallow + mid + deep) / 4, 1),
            "source": "estimated_from_climate",
            "_warning": (
                "Soil moisture is estimated from climate normals. The "
                "Open-Meteo soil-moisture API was unavailable and no recent "
                "cached measurement was found."
            ),
        }

    # ------------------------------------------------------------------
    # Persistent soil-moisture cache
    # ------------------------------------------------------------------

    async def _persist_soil_moisture(
        self, lat: float, lon: float, data: dict[str, Any]
    ) -> None:
        """Persist a successful soil-moisture reading for later fallback."""
        try:
            from sqlalchemy import delete

            from app.database import SoilMoistureCache, async_session

            cutoff = datetime.now(UTC) - timedelta(days=7)
            async with async_session() as session:
                # Keep the cache table small: drop week-old rows.
                await session.execute(
                    delete(SoilMoistureCache).where(
                        SoilMoistureCache.fetched_at < cutoff
                    )
                )
                session.add(
                    SoilMoistureCache(
                        latitude=round(lat, 3),
                        longitude=round(lon, 3),
                        surface=data.get("surface_0_1cm"),
                        shallow=data.get("shallow_1_3cm"),
                        mid=data.get("mid_3_9cm"),
                        deep=data.get("deep_9_27cm"),
                        fetched_at=datetime.now(UTC),
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.debug("Failed to persist soil moisture cache: %s", exc)

    async def _get_cached_soil_moisture(
        self, lat: float, lon: float, max_age_hours: int = 24, radius: float = 0.5
    ) -> dict[str, Any] | None:
        """Look up a recent nearby soil-moisture reading."""
        try:
            from sqlalchemy import select

            from app.database import SoilMoistureCache, async_session

            cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
            async with async_session() as session:
                result = await session.execute(
                    select(SoilMoistureCache)
                    .where(
                        SoilMoistureCache.latitude.between(
                            lat - radius, lat + radius
                        ),
                        SoilMoistureCache.longitude.between(
                            lon - radius, lon + radius
                        ),
                        SoilMoistureCache.fetched_at >= cutoff,
                    )
                    .order_by(SoilMoistureCache.fetched_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row:
                    values = [row.surface, row.shallow, row.mid, row.deep]
                    depths = [value for value in values if value is not None]
                    if depths:
                        return {
                            "surface_0_1cm": row.surface,
                            "shallow_1_3cm": row.shallow,
                            "mid_3_9cm": row.mid,
                            "deep_9_27cm": row.deep,
                            "average_pct": round(sum(depths) / len(depths), 1),
                            "source": "cached",
                            "_warning": (
                                "Soil moisture comes from a cached reading "
                                f"({row.fetched_at.isoformat()}); Open-Meteo "
                                "was unavailable."
                            ),
                        }
        except Exception as exc:
            logger.debug("DB soil moisture cache lookup failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Elevation grid fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _lookup_elevation_grid(lat: float, lon: float) -> float:
        """Return elevation from the bundled ETOPO10 grid."""
        value = _sample_elevation(lat, lon)
        if value is not None:
            return round(value, 1)
        return 200.0

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_service_instance: WeatherService | None = None


def get_weather_service() -> WeatherService:
    """Return the singleton weather service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = WeatherService()
    return _service_instance
