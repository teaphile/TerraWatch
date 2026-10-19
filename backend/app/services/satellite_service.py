"""Vegetation-index estimation service.

NDVI is a required input for the erosion and wildfire models. This project
does not ship a live satellite feed: MODIS/Landsat products are distributed
as GeoTIFF/NetCDF assets that need dedicated tiling and raster tooling, and
the public Web Coverage Service endpoints that used to provide point
samples are unreliable.

Rather than pretend to fetch imagery, this service computes a transparent
estimate from land-cover class and the bundled Köppen-Geiger climatology.
Every result is tagged ``source="estimated"`` with an explicit warning so
the API's data-quality reporting stays truthful.

To enable real NDVI later, implement a fetcher here that returns
``{"ndvi": float, "source": "modis", ...}`` and call it from :meth:`get_ndvi`
before falling back to :meth:`estimate_ndvi`.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Typical growing-season NDVI by land-cover class.
_NDVI_BY_LAND_COVER = {
    "forest": 0.70,
    "dense_forest": 0.80,
    "grassland": 0.45,
    "cropland": 0.50,
    "shrubland": 0.35,
    "wetland": 0.55,
    "bare": 0.10,
    "urban": 0.15,
    "water": -0.05,
}


class SatelliteService:
    """Estimate vegetation indices when no satellite feed is configured."""

    async def get_ndvi(
        self,
        latitude: float,
        longitude: float,
        land_cover: str = "unknown",
    ) -> dict[str, Any]:
        """Return NDVI for a location, with source attribution."""
        return self.estimate_ndvi(latitude, longitude, land_cover)

    def estimate_ndvi(
        self,
        latitude: float,
        longitude: float,
        land_cover: str = "unknown",
    ) -> dict[str, Any]:
        """Estimate NDVI from land cover, precipitation and temperature.

        Land cover is the dominant control; very wet and very dry climates
        push the value up or down respectively.
        """
        base_ndvi = _NDVI_BY_LAND_COVER.get(land_cover.lower(), 0.40)
        climate_class: str | None = None

        try:
            from app.services.weather_service import _interpolate_climate

            climate = _interpolate_climate(latitude, longitude)
            if climate:
                climate_class = climate.get("_class")
                precip = float(climate.get("p", 800))
                temp = float(climate.get("t", 15))
                if precip > 1200 and temp > 15:
                    base_ndvi *= 1.15
                elif precip > 800 and temp > 10:
                    base_ndvi *= 1.05
                elif precip < 300:
                    base_ndvi *= 0.65
                elif precip < 500:
                    base_ndvi *= 0.80
        except Exception as exc:
            logger.debug("NDVI climate adjustment skipped: %s", exc)

        ndvi = max(-0.1, min(0.95, base_ndvi))

        return {
            "ndvi": round(ndvi, 3),
            "source": "estimated",
            "land_cover": land_cover,
            "climate_class": climate_class,
            "_warning": (
                f"NDVI estimated from land cover ('{land_cover}') and "
                "Köppen-Geiger climate normals. No live satellite NDVI "
                "feed is configured."
            ),
        }

    async def close(self) -> None:
        """Release resources (no-op; kept for lifecycle symmetry)."""


_instance: SatelliteService | None = None


def get_satellite_service() -> SatelliteService:
    """Get the singleton satellite service."""
    global _instance
    if _instance is None:
        _instance = SatelliteService()
    return _instance
