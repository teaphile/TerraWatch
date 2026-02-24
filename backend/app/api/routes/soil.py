"""Soil analysis API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.soil_service import get_soil_service
from app.services.weather_service import get_weather_service

router = APIRouter(prefix="/soil", tags=["Soil Analysis"])


@router.get("/analyze")
async def analyze_soil(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    elevation: float | None = Query(None, ge=-500, le=9000, description="Elevation in meters"),
    land_cover: str = Query("cropland", description="Land cover type"),
) -> dict:
    """Get comprehensive soil analysis for a geographic point.

    Analyzes soil properties, erosion risk, health index, and carbon
    sequestration potential for the specified location.

    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **elevation**: Optional elevation in meters
    - **land_cover**: Land cover type (cropland, forest, grassland, etc.)
    """
    try:
        service = get_soil_service()
        result = await service.analyze(
            latitude=lat,
            longitude=lon,
            elevation=elevation,
            land_cover=land_cover,
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/moisture")
async def get_soil_moisture(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict:
    """Get current soil moisture data for a location.

    Returns soil moisture at multiple depths from Open-Meteo API.
    """
    try:
        weather = get_weather_service()
        result = await weather.get_soil_moisture(lat, lon)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
