"""Risk assessment API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.disaster_service import get_disaster_service
from app.data.ingestion.earthquake_fetcher import get_earthquake_fetcher

router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


@router.get("/all")
async def assess_all_risks(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> JSONResponse:
    """Get comprehensive multi-hazard risk assessment.

    Evaluates landslide, flood, liquefaction, and wildfire risks
    for the specified location using real-time weather data.

    Response includes a `data_quality` object with source tracking.
    """
    try:
        service = get_disaster_service()
        result = await service.assess_all_risks(latitude=lat, longitude=lon)

        data_quality = result.get("data_quality", {})
        warnings = data_quality.get("warnings", [])

        response = JSONResponse(
            content={"status": "success", "data": result}
        )

        if warnings:
            response.headers["X-Data-Quality-Warnings"] = "; ".join(warnings[:3])
        if not data_quality.get("is_fully_real_data", False):
            response.headers["X-Data-Contains-Estimates"] = "true"

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/landslide")
async def assess_landslide(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: float = Query(10.0, ge=0.1, le=500, description="Radius in km"),
) -> dict:
    """Get landslide risk assessment for a location.

    Returns probability, risk level, and contributing factors.
    """
    try:
        service = get_disaster_service()
        result = await service.assess_landslide(lat, lon, radius)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flood")
async def assess_flood(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict:
    """Get flood risk assessment for a location.

    Returns probability, return period, and inundation depth estimate.
    """
    try:
        service = get_disaster_service()
        result = await service.assess_flood(lat, lon)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/earthquake/recent")
async def get_recent_earthquakes(
    days: int = Query(1, ge=1, le=30, description="Number of days"),
    min_magnitude: float = Query(2.5, ge=0, le=10),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Get recent earthquakes from USGS.

    Returns real-time earthquake data from the USGS Earthquake Hazards API.
    """
    try:
        fetcher = get_earthquake_fetcher()
        events = await fetcher.fetch_recent(days, min_magnitude, limit)
        return {
            "status": "success",
            "data": {
                "count": len(events),
                "events": events,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
