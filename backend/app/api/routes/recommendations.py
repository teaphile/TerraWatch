"""Recommendation API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.soil_service import get_soil_service
from app.services.disaster_service import get_disaster_service
from app.services.recommendation_service import get_recommendation_service

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/agriculture")
async def get_agriculture_recommendations(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict:
    """Get agricultural recommendations for a location.

    Returns suitable crops, fertilizer recommendations, irrigation
    schedule, and soil amendment suggestions based on soil analysis.
    """
    try:
        soil_service = get_soil_service()
        rec_service = get_recommendation_service()

        soil = await soil_service.analyze(latitude=lat, longitude=lon)
        recs = rec_service.get_agricultural_recommendations(
            soil, soil.get("climate")
        )
        return {"status": "success", "data": recs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/disaster")
async def get_disaster_recommendations(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict:
    """Get disaster preparedness recommendations.

    Returns mitigation measures and preparedness actions based
    on the multi-hazard risk assessment.
    """
    try:
        disaster_service = get_disaster_service()
        rec_service = get_recommendation_service()

        risk = await disaster_service.assess_all_risks(latitude=lat, longitude=lon)
        recs = rec_service.get_disaster_recommendations(risk)
        return {"status": "success", "data": recs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/environmental")
async def get_environmental_recommendations(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict:
    """Get environmental restoration recommendations.

    Returns reforestation suitability, carbon sequestration potential,
    and soil remediation strategies.
    """
    try:
        soil_service = get_soil_service()
        rec_service = get_recommendation_service()

        soil = await soil_service.analyze(latitude=lat, longitude=lon)
        recs = rec_service.get_environmental_recommendations(soil)
        return {"status": "success", "data": recs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
