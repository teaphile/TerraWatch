"""Soil data fetcher for ISRIC SoilGrids API."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

SOILGRIDS_API = "https://rest.isric.org/soilgrids/v2.0"


class SoilFetcher:
    """Fetches soil data from ISRIC SoilGrids REST API."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = CacheService(maxsize=200, ttl=86400)  # 24h cache

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_properties(
        self, latitude: float, longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Fetch soil properties from SoilGrids.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.

        Returns:
            Soil property data or None if unavailable.
        """
        cache_key = f"soilgrids_{round(latitude, 2)}_{round(longitude, 2)}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{SOILGRIDS_API}/properties/query",
                params={
                    "lon": longitude,
                    "lat": latitude,
                    "property": "phh2o,soc,nitrogen,sand,silt,clay,cec,bdod",
                    "depth": "0-5cm,5-15cm,15-30cm",
                    "value": "mean",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                result = self._parse_response(data)
                self._cache.set(cache_key, result)
                return result
        except Exception as e:
            logger.warning(f"SoilGrids API failed: {e}")

        return None

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SoilGrids API response."""
        properties = data.get("properties", {})
        layers = properties.get("layers", [])

        result = {}
        for layer in layers:
            name = layer.get("name", "")
            depths = layer.get("depths", [])
            if depths:
                values = depths[0].get("values", {})
                mean_val = values.get("mean")
                if mean_val is not None:
                    result[name] = mean_val

        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_instance: Optional[SoilFetcher] = None


def get_soil_fetcher() -> SoilFetcher:
    global _instance
    if _instance is None:
        _instance = SoilFetcher()
    return _instance
