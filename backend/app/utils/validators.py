"""Input validation using Pydantic models."""
from __future__ import annotations
from typing import Any, Optional, List
from pydantic import BaseModel, Field, field_validator


class CoordinateInput(BaseModel):
    """Validated coordinate input."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class SoilAnalysisInput(BaseModel):
    """Input for soil analysis endpoint."""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    elevation: Optional[float] = Field(None, ge=-500, le=9000)
    land_cover: str = Field("cropland", description="Land cover type")

    @field_validator("land_cover")
    @classmethod
    def validate_land_cover(cls, v: str) -> str:
        valid = {"cropland", "forest", "grassland", "shrubland", "urban", "bare", "water", "wetland"}
        if v.lower() not in valid:
            v = "cropland"
        return v.lower()


class RiskAssessmentInput(BaseModel):
    """Input for risk assessment endpoint."""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(10.0, ge=0.1, le=500)


class AreaAnalysisInput(BaseModel):
    """Input for area analysis (GeoJSON polygon)."""
    type: str = Field("Polygon")
    coordinates: List[List[List[float]]] = Field(..., description="GeoJSON polygon coordinates")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("Polygon", "MultiPolygon"):
            raise ValueError("Type must be Polygon or MultiPolygon")
        return v


class AlertQueryInput(BaseModel):
    """Input for alert queries."""
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
