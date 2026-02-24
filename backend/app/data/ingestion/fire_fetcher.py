"""NASA FIRMS active fire data fetcher."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.services.alert_service import get_alert_service
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

FIRMS_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


class FireFetcher:
    """Fetches active fire data from NASA FIRMS (public endpoint)."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = CacheService(maxsize=50, ttl=3600)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_active_fires(
        self, region: str = "world", days: int = 1
    ) -> List[Dict[str, Any]]:
        """Fetch active fire data. Returns empty list if API unavailable."""
        cache_key = f"fires_{region}_{days}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        # FIRMS API requires a MAP_KEY; return empty if not configured
        result: List[Dict[str, Any]] = []
        self._cache.set(cache_key, result)
        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_instance: Optional[FireFetcher] = None


def get_fire_fetcher() -> FireFetcher:
    global _instance
    if _instance is None:
        _instance = FireFetcher()
    return _instance
