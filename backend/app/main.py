"""TerraWatch -- FastAPI Application Entry Point.

Global Real-Time Soil & Natural Disaster Risk Monitoring Platform.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.api.routes import soil, risk, recommendations, alerts, export, websocket
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.data.ingestion.earthquake_fetcher import get_earthquake_fetcher

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Background task handle
_bg_task = None


async def periodic_earthquake_fetch() -> None:
    """Periodically fetch earthquake data in the background."""
    fetcher = get_earthquake_fetcher()
    while True:
        try:
            events = await fetcher.fetch_recent(days=1, min_magnitude=4.0, limit=50)
            logger.info(f"Fetched {len(events)} recent earthquakes")
        except Exception as e:
            logger.error(f"Earthquake fetch error: {e}")
        await asyncio.sleep(settings.EARTHQUAKE_FETCH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    logger.info("Database initialized")

    # Start background earthquake fetching
    global _bg_task
    if settings.USGS_API_ENABLED:
        _bg_task = asyncio.create_task(periodic_earthquake_fetch())
        logger.info("Background earthquake fetcher started")

    yield

    # Shutdown
    if _bg_task:
        _bg_task.cancel()
        try:
            await _bg_task
        except asyncio.CancelledError:
            pass

    # Close HTTP clients
    eq_fetcher = get_earthquake_fetcher()
    await eq_fetcher.close()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Global Real-Time Soil Health Monitoring & Natural Disaster Risk "
        "Analysis Platform. Provides comprehensive soil analysis, "
        "multi-hazard risk assessment, and data-driven recommendations."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)

# API routes
app.include_router(soil.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(websocket.router)


@app.get("/api/v1/info", tags=["Health"])
async def api_info() -> dict:
    """API status and endpoint directory."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "soil_analysis": "/api/v1/soil/analyze?lat={lat}&lon={lon}",
            "risk_assessment": "/api/v1/risk/all?lat={lat}&lon={lon}",
            "landslide_risk": "/api/v1/risk/landslide?lat={lat}&lon={lon}",
            "flood_risk": "/api/v1/risk/flood?lat={lat}&lon={lon}",
            "earthquakes": "/api/v1/risk/earthquake/recent?days={n}",
            "agriculture_recs": "/api/v1/recommendations/agriculture?lat={lat}&lon={lon}",
            "alerts": "/api/v1/alerts/active",
            "websocket": "/ws/alerts",
        },
    }


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    from app.services.cache_service import get_soil_cache, get_risk_cache
    from app.services.alert_service import get_alert_service

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "cache": {
            "soil": get_soil_cache().stats,
            "risk": get_risk_cache().stats,
        },
        "alerts": get_alert_service().stats,
    }


@app.get("/api/v1/timeseries/soil-moisture", tags=["Time Series"])
async def soil_moisture_timeseries(
    lat: float,
    lon: float,
    days: int = 30,
) -> dict:
    """Get historical soil moisture time series data."""
    from app.services.weather_service import get_weather_service
    weather = get_weather_service()
    data = await weather.get_historical_data(lat, lon, days)
    return {"status": "success", "data": data}


@app.get("/api/v1/data-quality", tags=["Data Quality"])
async def data_quality_report(
    lat: float = Query(0.0, ge=-90, le=90, description="Latitude (-90 to 90)"),
    lon: float = Query(0.0, ge=-180, le=180, description="Longitude (-180 to 180)"),
) -> dict:
    """Report on data source availability and quality.

    Returns information about which data sources are live,
    which are using fallback/estimated values, and overall
    data quality assessment for the platform.
    """
    from app.services.weather_service import get_weather_service
    from app.data.ingestion.soil_fetcher import get_soil_fetcher

    sources = {}
    warnings = []

    # Check ISRIC SoilGrids
    try:
        fetcher = get_soil_fetcher()
        isric_data = await fetcher.fetch_properties(lat, lon)
        sources["isric_soilgrids"] = {
            "status": "available" if isric_data else "unavailable",
            "description": "ISRIC SoilGrids v2.0 -- 250m resolution global soil properties",
            "url": "https://rest.isric.org/soilgrids/v2.0",
        }
        if not isric_data:
            warnings.append("ISRIC SoilGrids API returned no data -- soil properties will use analytical estimation.")
    except Exception as e:
        sources["isric_soilgrids"] = {"status": "error", "error": str(e)}
        warnings.append(f"ISRIC SoilGrids API error: {e}")

    # Check Open-Meteo
    try:
        wx = get_weather_service()
        weather = await wx.get_current_weather(lat, lon)
        sources["open_meteo_weather"] = {
            "status": "live" if weather.get("source") == "open-meteo" else "fallback",
            "description": "Open-Meteo -- free weather API (no key required)",
            "url": "https://api.open-meteo.com/v1",
        }
        if weather.get("source") != "open-meteo":
            warnings.append("Open-Meteo weather API unavailable -- using latitude-based estimates.")

        moisture = await wx.get_soil_moisture(lat, lon)
        sources["open_meteo_soil_moisture"] = {
            "status": "live" if moisture.get("source") == "open-meteo" else "fallback",
            "description": "Open-Meteo soil moisture at multiple depths",
        }
    except Exception as e:
        sources["open_meteo"] = {"status": "error", "error": str(e)}

    # Check USGS
    sources["usgs_earthquakes"] = {
        "status": "enabled" if settings.USGS_API_ENABLED else "disabled",
        "description": "USGS Earthquake Hazards Program real-time feed",
        "url": "https://earthquake.usgs.gov/fdsnws/event/1",
    }

    # ML model status
    from app.models.soil_model import get_soil_model
    model = get_soil_model()
    sources["soil_ml_model"] = {
        "status": "trained" if model.is_trained else "not_available",
        "description": (
            "Random Forest + XGBoost ensemble for soil prediction"
            if model.is_trained
            else "No trained model available -- using analytical heuristics"
        ),
    }
    if not model.is_trained:
        warnings.append(
            "No trained ML model for soil prediction. All soil properties "
            "come from ISRIC SoilGrids API or analytical estimation. "
            "The soil_ensemble.joblib file does not exist."
        )

    # NDVI/Satellite status
    sources["ndvi_satellite"] = {
        "status": "estimated",
        "description": (
            "NDVI is estimated from latitude heuristics when OpenLandMap "
            "or Sentinel-2 data is not available."
        ),
    }

    # FIRMS fire data
    sources["nasa_firms"] = {
        "status": "available" if getattr(settings, "FIRMS_MAP_KEY", "") else "limited",
        "description": (
            "NASA FIRMS active fire data. Full API requires MAP_KEY."
        ),
    }

    # Overall quality
    live_count = sum(
        1 for s in sources.values()
        if s.get("status") in ("available", "live", "enabled", "trained")
    )
    total_count = len(sources)

    return {
        "status": "success",
        "data": {
            "overall_quality": (
                "good" if live_count >= 4
                else "moderate" if live_count >= 2
                else "limited"
            ),
            "live_sources": live_count,
            "total_sources": total_count,
            "sources": sources,
            "warnings": warnings,
            "transparency_note": (
                "TerraWatch uses multiple external APIs for real data. "
                "When an API is unavailable, analytical fallback values "
                "are used. The 'source' field in every API response "
                "indicates whether data is real or estimated. "
                "The data_quality object provides detailed source tracking."
            ),
        },
    }


@app.post("/api/v1/area/analyze", tags=["Area Analysis"])
async def analyze_area(body: dict) -> dict:
    """Analyze a custom polygon area (GeoJSON body).

    Accepts a GeoJSON polygon and returns analysis for sample points
    within the polygon.
    """
    from app.services.soil_service import get_soil_service

    coordinates = body.get("coordinates", [])
    if not coordinates:
        return {"status": "error", "detail": "No coordinates provided"}

    # Get centroid of polygon for analysis
    ring = coordinates[0] if coordinates else []
    if not ring:
        return {"status": "error", "detail": "Empty polygon"}

    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    centroid_lat = sum(lats) / len(lats)
    centroid_lon = sum(lons) / len(lons)

    service = get_soil_service()
    result = await service.analyze(latitude=centroid_lat, longitude=centroid_lon)

    return {
        "status": "success",
        "data": {
            "centroid": {"lat": centroid_lat, "lon": centroid_lon},
            "analysis": result,
            "polygon_area_km2": _polygon_area(ring),
        },
    }


def _polygon_area(ring: list) -> float:
    """Estimate polygon area in km² using shoelace formula."""
    import math
    n = len(ring)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += ring[i][0] * ring[j][1]
        area -= ring[j][0] * ring[i][1]
    area = abs(area) / 2.0
    # Convert from deg² to km² (approximate)
    avg_lat = sum(p[1] for p in ring) / n
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(avg_lat))
    return round(area * km_per_deg_lat * km_per_deg_lon, 2)


# Serve frontend static files if available
# Check multiple possible locations (dev layout vs Docker layout)
_possible_dist = [
    Path(__file__).parent.parent.parent / "frontend" / "dist",  # dev: backend/app/main.py -> frontend/dist
    Path(__file__).parent.parent / "frontend" / "dist",         # docker: /app/app/main.py -> /app/frontend/dist
]
frontend_dist = next((p for p in _possible_dist if p.exists()), None)

if frontend_dist is not None:
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve frontend SPA for unmatched routes."""
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"detail": "Not found"}, status_code=404)
