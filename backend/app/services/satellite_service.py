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
    def _estimate_ndvi(
        latitude: float,
        longitude: float,
        land_cover: str = "unknown",
    ) -> Dict[str, Any]:
        """Estimate NDVI from land cover type and climate context.

        Uses land cover as the primary indicator (much more meaningful
        than latitude alone), with seasonal/climate adjustments from
        the climate normals dataset.
        """
        # Land-cover-based NDVI (primary factor)
        ndvi_by_cover = {
            "forest": 0.70, "dense_forest": 0.80,
            "grassland": 0.45, "cropland": 0.50,
            "shrubland": 0.35, "wetland": 0.55,
            "bare": 0.10, "urban": 0.15, "water": -0.05,
        }
        base_ndvi = ndvi_by_cover.get(land_cover.lower(), 0.40)

        # Climate adjustment from normals
        try:
            from app.services.weather_service import _interpolate_climate
            climate = _interpolate_climate(latitude, longitude)
            if climate:
                precip = climate.get("p", 800)
                temp = climate.get("t", 15)
                # Wetter & warmer → greener (up to a point)
                if precip > 1200 and temp > 15:
                    base_ndvi *= 1.15
                elif precip > 800 and temp > 10:
                    base_ndvi *= 1.05
                elif precip < 300:
                    base_ndvi *= 0.65
                elif precip < 500:
                    base_ndvi *= 0.80
        except Exception:
            pass

        ndvi = max(-0.1, min(0.95, base_ndvi))

        return {
            "ndvi": round(ndvi, 3),
            "source": "estimated",
            "_warning": (
                f"NDVI estimated from land cover type ('{land_cover}') and "
                "climate normals. NOT from real satellite imagery. "
                "OpenLandMap API was unavailable."
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
