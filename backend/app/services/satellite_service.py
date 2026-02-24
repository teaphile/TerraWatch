"""Satellite data processing service (stub for extensibility)."""

from __future__ import annotations
from typing import Any, Dict, Optional


class SatelliteService:
    """Service for satellite data processing.

    Provides NDVI calculation and satellite imagery integration.
    Currently uses analytical estimation; can be extended with
    real satellite data APIs (Sentinel-2, MODIS).
    """

    async def get_ndvi(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Get NDVI for a location (estimated)."""
        import math
        abs_lat = abs(latitude)
        # Rough estimation
        if abs_lat < 15:
            ndvi = 0.6
        elif abs_lat < 30:
            ndvi = 0.4
        elif abs_lat < 50:
            ndvi = 0.55
        else:
            ndvi = 0.3

        ndvi += math.sin(longitude * 0.05) * 0.1
        return {
            "ndvi": round(max(0, min(1, ndvi)), 3),
            "source": "estimated",
        }


_instance: Optional[SatelliteService] = None


def get_satellite_service() -> SatelliteService:
    """Get singleton satellite service."""
    global _instance
    if _instance is None:
        _instance = SatelliteService()
    return _instance
