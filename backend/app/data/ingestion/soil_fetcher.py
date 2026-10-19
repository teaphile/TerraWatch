"""Soil data fetcher for ISRIC SoilGrids API."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

SOILGRIDS_API = "https://rest.isric.org/soilgrids/v2.0"


class SoilFetcher:
    """Fetches soil data from ISRIC SoilGrids REST API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._cache = CacheService(maxsize=200, ttl=86400)  # 24h cache

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(12.0, connect=5.0),
                headers={"User-Agent": "TerraWatch/2.0"},
            )
        return self._client

    async def fetch_properties(
        self, latitude: float, longitude: float
    ) -> dict[str, Any] | None:
        """Fetch soil properties from SoilGrids.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.

        Returns:
            Soil property data or None if unavailable.
        """
        cache_key = self._cache.make_key(
            "soilgrids", lat=round(latitude, 2), lon=round(longitude, 2)
        )
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            # SoilGrids expects repeated ``property``/``depth`` parameters
            # (OpenAPI array with explode=true), not comma-separated values.
            params: list[tuple[str, str | float]] = [
                ("lon", longitude),
                ("lat", latitude),
                ("value", "mean"),
            ]
            params += [
                ("property", name)
                for name in (
                    "phh2o",
                    "soc",
                    "nitrogen",
                    "sand",
                    "silt",
                    "clay",
                    "cec",
                    "bdod",
                )
            ]
            params += [
                ("depth", depth)
                for depth in ("0-5cm", "5-15cm", "15-30cm")
            ]
            resp = await client.get(
                f"{SOILGRIDS_API}/properties/query", params=params
            )
            if resp.status_code == 200:
                data = resp.json()
                result = self._parse_response(data)
                self._cache.set(cache_key, result)
                return result
        except Exception as e:
            logger.warning(f"SoilGrids API failed: {e}")

        return None

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse SoilGrids response into 0-30 cm thickness-weighted means.

        SoilGrids returns one value per depth interval. The soil models in
        this project work on the top 30 cm, so the 0-5, 5-15 and 15-30 cm
        layers are averaged with weights 5, 10 and 15.
        """
        layer_weights = {"0-5cm": 5.0, "5-15cm": 10.0, "15-30cm": 15.0}
        properties = data.get("properties", {})
        layers = properties.get("layers", [])

        result: dict[str, float] = {}
        for layer in layers:
            name = layer.get("name", "")
            total_weight = 0.0
            weighted_sum = 0.0
            for depth in layer.get("depths", []):
                label = str(depth.get("label", ""))
                weight = layer_weights.get(label, 0.0)
                mean_val = depth.get("values", {}).get("mean")
                if weight and mean_val is not None:
                    weighted_sum += float(mean_val) * weight
                    total_weight += weight
            if total_weight:
                result[name] = round(weighted_sum / total_weight, 3)

        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_instance: SoilFetcher | None = None


def get_soil_fetcher() -> SoilFetcher:
    global _instance
    if _instance is None:
        _instance = SoilFetcher()
    return _instance
