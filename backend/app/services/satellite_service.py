"""Satellite data processing service.

Provides NDVI data from real satellite sources when available,
with transparent fallback to analytical estimation.

Data source priority:
1. OpenLandMap NDVI (free, no key required, MODIS-derived)
2. Analytical estimation (latitude + land cover heuristics) -- clearly marked
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# OpenLandMap provides open MODIS-derived NDVI data
OPENLANDMAP_WCS = "https://geoserver.openlandmap.org/geoserver/ows"


class SatelliteService:
    """Service for satellite data processing.

    Provides NDVI calculation and satellite imagery integration.
    Attempts to fetch from real satellite data APIs first,
    falls back to analytical estimation with clear warnings.
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def get_ndvi(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Get NDVI for a location.

        Tries real satellite data sources first, falls back to estimation.
        """
        # Try OpenLandMap MODIS NDVI first
        try:
            result = await self._fetch_openlandmap_ndvi(latitude, longitude)
            if result is not None:
                return result
        except Exception as e:
            logger.warning(f"OpenLandMap NDVI fetch failed: {e}")

        # Fall back to analytical estimation
        return self._estimate_ndvi(latitude, longitude)

    async def _fetch_openlandmap_ndvi(
        self, latitude: float, longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Fetch MODIS-derived NDVI from OpenLandMap.

        OpenLandMap serves global MODIS NDVI composites via OGC WCS.
        Returns None if unavailable.
        """
        client = await self._get_client()
        try:
            resp = await client.get(
                OPENLANDMAP_WCS,
                params={
                    "service": "WCS",
                    "version": "2.0.1",
                    "request": "GetCoverage",
                    "CoverageId": "modis_ndvi_250m",
                    "subset": f"Long({longitude - 0.005},{longitude + 0.005})",
                    "subset2": f"Lat({latitude - 0.005},{latitude + 0.005})",
                    "format": "application/json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                ndvi_value = self._parse_openlandmap_ndvi(data)
                if ndvi_value is not None:
                    return {
                        "ndvi": round(max(0, min(1, ndvi_value)), 3),
                        "source": "openlandmap_modis",
                        "resolution_m": 250,
                        "_source_detail": "MODIS NDVI 250m composite via OpenLandMap",
                    }
        except Exception as e:
            logger.debug(f"OpenLandMap WCS request failed: {e}")

        return None

    @staticmethod
    def _parse_openlandmap_ndvi(data: Dict[str, Any]) -> Optional[float]:
        """Parse NDVI value from OpenLandMap WCS response."""
        try:
            if isinstance(data, dict):
                values = data.get("values", data.get("data", []))
                if isinstance(values, list) and values:
                    val = values[0]
                    if isinstance(val, (int, float)):
                        return val / 10000.0 if val > 1 else val
            return None
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _estimate_ndvi(latitude: float, longitude: float) -> Dict[str, Any]:
        """Estimate NDVI from latitude/longitude heuristics.

        WARNING: This is a CRUDE estimation. Values are NOT derived
        from satellite imagery and should not be used for research.
        """
        import math
        abs_lat = abs(latitude)
        if abs_lat < 15:
            ndvi = 0.6  # Tropical
        elif abs_lat < 30:
            ndvi = 0.4  # Subtropical/arid
        elif abs_lat < 50:
            ndvi = 0.55  # Temperate
        else:
            ndvi = 0.3  # Boreal/Arctic

        # Small longitude variation (placeholder, NOT scientifically valid)
        ndvi += math.sin(longitude * 0.05) * 0.05

        return {
            "ndvi": round(max(0, min(1, ndvi)), 3),
            "source": "estimated",
            "_warning": (
                "NDVI is estimated from latitude-based heuristics, NOT from "
                "real satellite imagery. Values should not be used for "
                "research or precision agriculture."
            ),
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_instance: Optional[SatelliteService] = None


def get_satellite_service() -> SatelliteService:
    """Get singleton satellite service."""
    global _instance
    if _instance is None:
        _instance = SatelliteService()
    return _instance
