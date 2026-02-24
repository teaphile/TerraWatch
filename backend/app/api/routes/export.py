"""Data export API endpoints."""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.services.soil_service import get_soil_service
from app.services.disaster_service import get_disaster_service

router = APIRouter(prefix="/export", tags=["Data Export"])


@router.get("/soil/csv")
async def export_soil_csv(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> StreamingResponse:
    """Export soil analysis as CSV."""
    try:
        service = get_soil_service()
        data = await service.analyze(latitude=lat, longitude=lon)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Property", "Value", "Confidence", "Unit"])
        props = data.get("soil_properties", {})

        writer.writerow(["pH", props.get("ph", {}).get("value"), props.get("ph", {}).get("confidence"), ""])
        writer.writerow(["Organic Carbon", props.get("organic_carbon_pct", {}).get("value"), props.get("organic_carbon_pct", {}).get("confidence"), "%"])
        writer.writerow(["Nitrogen", props.get("nitrogen_pct", {}).get("value"), props.get("nitrogen_pct", {}).get("confidence"), "%"])
        writer.writerow(["Moisture", props.get("moisture_pct", {}).get("value"), props.get("moisture_pct", {}).get("confidence"), "%"])
        texture = props.get("texture", {})
        writer.writerow(["Sand", texture.get("sand_pct"), "", "%"])
        writer.writerow(["Silt", texture.get("silt_pct"), "", "%"])
        writer.writerow(["Clay", texture.get("clay_pct"), "", "%"])
        writer.writerow(["Texture Class", texture.get("classification"), "", ""])
        writer.writerow(["Bulk Density", props.get("bulk_density_gcm3"), "", "g/cm³"])
        writer.writerow(["CEC", props.get("cec_cmolkg"), "", "cmol/kg"])

        erosion = data.get("erosion_risk", {})
        writer.writerow(["RUSLE Value", erosion.get("rusle_value_tons_ha_yr"), "", "tons/ha/yr"])
        writer.writerow(["Erosion Risk", erosion.get("risk_level"), "", ""])

        health = data.get("health_index", {})
        writer.writerow(["Health Score", health.get("score"), "", ""])
        writer.writerow(["Health Grade", health.get("grade"), "", ""])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=soil_analysis_{lat}_{lon}.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/soil/geojson")
async def export_soil_geojson(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> StreamingResponse:
    """Export soil analysis as GeoJSON Feature."""
    try:
        service = get_soil_service()
        data = await service.analyze(latitude=lat, longitude=lon)

        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "soil_properties": data.get("soil_properties"),
                "health_index": data.get("health_index"),
                "erosion_risk": data.get("erosion_risk"),
                "carbon_sequestration": data.get("carbon_sequestration"),
                "timestamp": data.get("timestamp"),
            },
        }
        content = json.dumps(geojson, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename=soil_{lat}_{lon}.geojson"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/geojson")
async def export_risk_geojson(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> StreamingResponse:
    """Export risk assessment as GeoJSON Feature."""
    try:
        service = get_disaster_service()
        data = await service.assess_all_risks(latitude=lat, longitude=lon)

        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "risks": data.get("risks"),
                "composite_risk_score": data.get("composite_risk_score"),
                "composite_risk_level": data.get("composite_risk_level"),
                "timestamp": data.get("timestamp"),
            },
        }
        content = json.dumps(geojson, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename=risk_{lat}_{lon}.geojson"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def export_full_report(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> StreamingResponse:
    """Export comprehensive JSON report with soil, risk, and recommendations."""
    try:
        from app.services.recommendation_service import get_recommendation_service

        soil_service = get_soil_service()
        disaster_service = get_disaster_service()
        rec_service = get_recommendation_service()

        soil = await soil_service.analyze(latitude=lat, longitude=lon)
        risk = await disaster_service.assess_all_risks(latitude=lat, longitude=lon)
        ag_recs = rec_service.get_agricultural_recommendations(soil, soil.get("climate"))
        disaster_recs = rec_service.get_disaster_recommendations(risk)
        env_recs = rec_service.get_environmental_recommendations(soil)

        report = {
            "report_type": "TerraWatch Full Analysis Report",
            "location": {"latitude": lat, "longitude": lon},
            "soil_analysis": soil,
            "risk_assessment": risk,
            "recommendations": {
                "agriculture": ag_recs,
                "disaster_preparedness": disaster_recs,
                "environmental_restoration": env_recs,
            },
        }

        content = json.dumps(report, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=terrawatch_report_{lat}_{lon}.json"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
