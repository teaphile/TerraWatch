"""NASA FIRMS active fire data fetcher.

Fetches active fire/hotspot data from NASA FIRMS.
Requires a MAP_KEY for the full API, but also supports
the public open data CSV endpoint for MODIS C6.1/VIIRS data.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

settings = get_settings()

# NASA FIRMS public open data endpoint (no key needed for recent 24h data)
FIRMS_OPEN_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv"
FIRMS_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


class FireFetcher:
    """Fetches active fire data from NASA FIRMS.

    Uses the public open data CSV endpoint (no API key required)
    for recent 24h global fire data. For historical or custom area
    queries, requires a FIRMS MAP_KEY.
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = CacheService(maxsize=50, ttl=3600)
        self._map_key = getattr(settings, "FIRMS_MAP_KEY", "")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_active_fires(
        self,
        region: str = "world",
        days: int = 1,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: float = 100.0,
    ) -> List[Dict[str, Any]]:
        """Fetch active fire data.

        First tries the FIRMS API with MAP_KEY, then falls back to
        the public open data endpoint. Returns empty list with a
        warning if both are unavailable.
        """
        cache_key = f"fires_{region}_{days}_{latitude}_{longitude}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        result: List[Dict[str, Any]] = []

        # Try FIRMS API if MAP_KEY is configured
        if self._map_key:
            try:
                result = await self._fetch_firms_api(
                    region, days, latitude, longitude, radius_km
                )
            except Exception as e:
                logger.warning(f"FIRMS API failed: {e}")

        # Try public open data endpoint if API didn't return results
        if not result and days <= 1:
            try:
                result = await self._fetch_public_fires(latitude, longitude, radius_km)
            except Exception as e:
                logger.warning(f"FIRMS public fire data fetch failed: {e}")

        if not result:
            logger.info(
                "No fire data available. FIRMS API requires a MAP_KEY for "
                "full access. Get one free at https://firms.modaps.eosdis.nasa.gov/api/area/"
            )

        self._cache.set(cache_key, result)
        return result

    async def _fetch_firms_api(
        self,
        region: str,
        days: int,
        latitude: Optional[float],
        longitude: Optional[float],
        radius_km: float,
    ) -> List[Dict[str, Any]]:
        """Fetch from FIRMS MAP API (requires key)."""
        client = await self._get_client()

        if latitude is not None and longitude is not None:
            # Point-based query
            url = (
                f"{FIRMS_API}/{self._map_key}/MODIS_NRT/"
                f"{longitude},{latitude},{radius_km}/{days}"
            )
        else:
            url = f"{FIRMS_API}/{self._map_key}/MODIS_NRT/{region}/{days}"

        resp = await client.get(url)
        if resp.status_code == 200:
            return self._parse_csv_response(resp.text)
        return []

    async def _fetch_public_fires(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        radius_km: float,
    ) -> List[Dict[str, Any]]:
        """Fetch from FIRMS public open data (last 24h, no key)."""
        client = await self._get_client()

        # The public endpoint provides global 24h data
        resp = await client.get(
            f"{FIRMS_OPEN_URL}/MODIS_C6_1_Global_24h.csv",
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return []

        fires = self._parse_csv_response(resp.text)

        # Filter to nearby fires if coordinates provided
        if latitude is not None and longitude is not None and fires:
            from app.utils.geo_utils import haversine
            fires = [
                f for f in fires
                if haversine(
                    latitude, longitude,
                    f.get("latitude", 0), f.get("longitude", 0)
                ) <= radius_km
            ]

        return fires[:100]  # Limit results

    @staticmethod
    def _parse_csv_response(csv_text: str) -> List[Dict[str, Any]]:
        """Parse FIRMS CSV response into list of fire events."""
        fires = []
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            for row in reader:
                try:
                    fires.append({
                        "latitude": float(row.get("latitude", 0)),
                        "longitude": float(row.get("longitude", 0)),
                        "brightness": float(row.get("brightness", 0)),
                        "confidence": row.get("confidence", ""),
                        "frp": float(row.get("frp", 0)),
                        "acq_date": row.get("acq_date", ""),
                        "acq_time": row.get("acq_time", ""),
                        "satellite": row.get("satellite", ""),
                        "daynight": row.get("daynight", ""),
                        "source": "nasa_firms",
                    })
                except (ValueError, KeyError):
                    continue
        except Exception:
            pass
        return fires

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_instance: Optional[FireFetcher] = None


def get_fire_fetcher() -> FireFetcher:
    global _instance
    if _instance is None:
        _instance = FireFetcher()
    return _instance
