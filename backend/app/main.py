"""TerraWatch -- FastAPI application entry point.

Global real-time soil health and natural-disaster risk monitoring platform.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.middleware.auth import APIKeyMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.routes import alerts, export, recommendations, risk, soil, websocket
from app.config import get_settings
from app.data.ingestion.earthquake_fetcher import get_earthquake_fetcher
from app.database import init_db

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_STARTED_AT = time.time()
_bg_task: asyncio.Task | None = None


async def periodic_earthquake_fetch() -> None:
    """Fetch recent earthquakes in the background and raise alerts."""
    fetcher = get_earthquake_fetcher()
    while True:
        try:
            events = await fetcher.fetch_recent(
                days=1, min_magnitude=4.0, limit=50
            )
            logger.info("Fetched %d recent earthquakes", len(events))
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception as exc:
            logger.error("Earthquake fetch error: %s", exc)
        await asyncio.sleep(settings.EARTHQUAKE_FETCH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    logger.info("Database initialized")

    global _bg_task
    if settings.USGS_API_ENABLED:
        _bg_task = asyncio.create_task(periodic_earthquake_fetch())
        logger.info("Background earthquake fetcher started")

    yield

    if _bg_task is not None:
        _bg_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _bg_task

    # Close every service that owns an HTTP connection pool.
    from app.data.ingestion.fire_fetcher import get_fire_fetcher
    from app.data.ingestion.soil_fetcher import get_soil_fetcher
    from app.services.satellite_service import get_satellite_service
    from app.services.weather_service import get_weather_service

    closers = [
        get_earthquake_fetcher().close(),
        get_weather_service().close(),
        get_soil_fetcher().close(),
        get_fire_fetcher().close(),
        get_satellite_service().close(),
    ]
    await asyncio.gather(*closers, return_exceptions=True)
    logger.info("Application shutdown complete")


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

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# Starlette wraps middleware in reverse order: the last one added is the
# outermost. Auth runs first (innermost), then rate limiting, then CORS so
# that every response -- including 401/429 -- carries CORS headers.
app.add_middleware(APIKeyMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Data-Quality-Warnings",
        "X-Data-Contains-Estimates",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "Retry-After",
    ],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(soil.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(websocket.router)


@app.get("/api/v1/info", tags=["Health"])
async def api_info() -> dict:
    """Return API status and an endpoint directory."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "endpoints": {
            "soil_analysis": "/api/v1/soil/analyze?lat={lat}&lon={lon}",
            "risk_assessment": "/api/v1/risk/all?lat={lat}&lon={lon}",
            "landslide_risk": "/api/v1/risk/landslide?lat={lat}&lon={lon}",
            "flood_risk": "/api/v1/risk/flood?lat={lat}&lon={lon}",
            "earthquakes": "/api/v1/risk/earthquake/recent?days={n}",
            "agriculture_recs": "/api/v1/recommendations/agriculture?lat={lat}&lon={lon}",
            "alerts": "/api/v1/alerts/active",
            "data_quality": "/api/v1/data-quality?lat={lat}&lon={lon}",
            "websocket": "/ws/alerts",
        },
    }


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> dict:
    """Return a lightweight health check with cache and alert statistics."""
    from app.services.alert_service import get_alert_service
    from app.services.cache_service import get_risk_cache, get_soil_cache

    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "cache": {
            "soil": get_soil_cache().stats,
            "risk": get_risk_cache().stats,
        },
        "alerts": get_alert_service().stats,
    }


@app.get("/api/v1/timeseries/soil-moisture", tags=["Time Series"])
async def soil_moisture_timeseries(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """Return historical weather and soil-moisture series for a location."""
    from app.services.weather_service import get_weather_service

    weather_service = get_weather_service()
    weather, moisture = await asyncio.gather(
        weather_service.get_historical_data(lat, lon, days),
        weather_service.get_soil_moisture_history(lat, lon, days),
    )
    return {
        "status": "success",
        "data": {**weather, "soil_moisture": moisture},
    }


@app.get("/api/v1/data-quality", tags=["Data Quality"])
async def data_quality_report(
    lat: float = Query(0.0, ge=-90, le=90, description="Latitude (-90 to 90)"),
    lon: float = Query(0.0, ge=-180, le=180, description="Longitude (-180 to 180)"),
) -> dict:
    """Report which data sources are live for a location.

    The checks run concurrently so a slow upstream API cannot hold up the
    report for tens of seconds.
    """
    from app.data.ingestion.soil_fetcher import get_soil_fetcher
    from app.models.soil_model import get_soil_model
    from app.services.weather_service import get_weather_service

    weather_service = get_weather_service()
    isric_result, weather_result, climate_result, moisture_result = (
        await asyncio.gather(
            get_soil_fetcher().fetch_properties(lat, lon),
            weather_service.get_current_weather(lat, lon),
            weather_service.get_climate_normals(lat, lon),
            weather_service.get_soil_moisture(lat, lon),
            return_exceptions=True,
        )
    )

    sources: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    if isinstance(isric_result, Exception):
        sources["isric_soilgrids"] = {
            "status": "error",
            "error": str(isric_result),
            "description": "ISRIC SoilGrids v2.0 -- 250 m global soil properties",
        }
        warnings.append(f"ISRIC SoilGrids API error: {isric_result}")
    else:
        sources["isric_soilgrids"] = {
            "status": "available" if isric_result else "unavailable",
            "description": "ISRIC SoilGrids v2.0 -- 250 m global soil properties",
            "url": "https://rest.isric.org/soilgrids/v2.0",
        }
        if not isric_result:
            warnings.append(
                "ISRIC SoilGrids API returned no data -- soil properties "
                "will use analytical estimation."
            )

    if isinstance(weather_result, Exception):
        sources["open_meteo_weather"] = {
            "status": "error",
            "error": str(weather_result),
        }
        warnings.append(f"Open-Meteo weather API error: {weather_result}")
    else:
        weather_source = weather_result.get("source")
        sources["open_meteo_weather"] = {
            "status": "live" if weather_source == "open-meteo" else "fallback",
            "description": "Open-Meteo -- free weather API (no key required)",
            "url": "https://api.open-meteo.com/v1",
        }
        if weather_source != "open-meteo":
            warnings.append(
                "Open-Meteo weather API unavailable -- using climate-based estimates."
            )

    if isinstance(climate_result, Exception):
        sources["open_meteo_climate"] = {
            "status": "error",
            "error": str(climate_result),
        }
    else:
        climate_source = climate_result.get("source")
        sources["open_meteo_climate"] = {
            "status": "live" if climate_source == "open-meteo" else "fallback",
            "description": "30-year climate normals from the Open-Meteo archive API",
        }
        if climate_source != "open-meteo":
            warnings.append(
                "Climate normals API unavailable -- using the built-in "
                "climatology lookup."
            )

    if isinstance(moisture_result, Exception):
        sources["open_meteo_soil_moisture"] = {
            "status": "error",
            "error": str(moisture_result),
        }
    else:
        moisture_source = moisture_result.get("source")
        sources["open_meteo_soil_moisture"] = {
            "status": "live" if moisture_source == "open-meteo" else "fallback",
            "description": "Open-Meteo soil moisture at multiple depths",
        }
        if moisture_source != "open-meteo":
            warnings.append(
                "Open-Meteo soil moisture is unavailable -- soil moisture is "
                f"estimated ({moisture_source}) instead of measured."
            )

    sources["usgs_earthquakes"] = {
        "status": "enabled" if settings.USGS_API_ENABLED else "disabled",
        "description": "USGS Earthquake Hazards Program real-time feed",
        "url": "https://earthquake.usgs.gov/fdsnws/event/1",
    }

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
            "No trained ML model for soil prediction is deployed. Soil "
            "properties come from ISRIC SoilGrids or analytical estimation."
        )

    sources["ndvi_satellite"] = {
        "status": "estimated",
        "description": (
            "NDVI is estimated from land-cover type and climate normals; "
            "no live satellite NDVI feed is configured."
        ),
    }
    sources["nasa_firms"] = {
        "status": "available" if settings.FIRMS_MAP_KEY else "limited",
        "description": (
            "NASA FIRMS active fire data. Set FIRMS_MAP_KEY for full access; "
            "the public 24 h feed is used otherwise."
        ),
    }

    live_statuses = {"available", "live", "enabled", "trained"}
    live_count = sum(
        1 for source in sources.values() if source.get("status") in live_statuses
    )

    return {
        "status": "success",
        "data": {
            "overall_quality": (
                "good"
                if live_count >= 4
                else "moderate"
                if live_count >= 2
                else "limited"
            ),
            "live_sources": live_count,
            "total_sources": len(sources),
            "sources": sources,
            "warnings": warnings,
            "transparency_note": (
                "TerraWatch uses multiple external APIs for real data. When "
                "an API is unavailable, analytical fallback values are used. "
                "The 'source' field in every API response indicates whether "
                "data is real or estimated, and the data_quality object "
                "provides detailed source tracking."
            ),
        },
    }


@app.post("/api/v1/area/analyze", tags=["Area Analysis"])
async def analyze_area(body: dict) -> dict:
    """Analyze a GeoJSON polygon and return results for its centroid."""
    from app.services.soil_service import get_soil_service

    ring = _extract_geojson_ring(body)
    if not ring:
        raise HTTPException(
            status_code=422,
            detail="Provide a GeoJSON Polygon or MultiPolygon with coordinates.",
        )
    if len(ring) < 3:
        raise HTTPException(
            status_code=422, detail="A polygon ring needs at least 3 points."
        )

    try:
        lons = [float(point[0]) for point in ring]
        lats = [float(point[1]) for point in ring]
    except (TypeError, ValueError, IndexError) as exc:
        raise HTTPException(
            status_code=422, detail="Polygon coordinates must be [lon, lat] pairs."
        ) from exc

    if not all(-90 <= value <= 90 for value in lats) or not all(
        -180 <= value <= 180 for value in lons
    ):
        raise HTTPException(status_code=422, detail="Polygon coordinates out of range.")

    centroid_lat = sum(lats) / len(lats)
    centroid_lon = sum(lons) / len(lons)

    result = await get_soil_service().analyze(
        latitude=centroid_lat, longitude=centroid_lon
    )

    return {
        "status": "success",
        "data": {
            "centroid": {
                "lat": round(centroid_lat, 6),
                "lon": round(centroid_lon, 6),
            },
            "analysis": result,
            "polygon_area_km2": _polygon_area(ring),
        },
    }


def _extract_geojson_ring(body: Any) -> list[list[float]] | None:
    """Extract the outer ring from a GeoJSON polygon body.

    Accepts either a full GeoJSON geometry/feature or a bare
    ``{"coordinates": [...]}`` object.
    """
    if not isinstance(body, dict):
        return None

    geometry = body.get("geometry") if body.get("type") == "Feature" else body
    if not isinstance(geometry, dict):
        return None

    coordinates = geometry.get("coordinates")
    if not coordinates:
        return None

    geom_type = str(geometry.get("type", "Polygon")).lower()
    if geom_type == "multipolygon":
        coordinates = coordinates[0]
    if not coordinates or not isinstance(coordinates[0], list):
        return None
    return coordinates[0]


def _polygon_area(ring: list[list[float]]) -> float:
    """Estimate polygon area in km² using the shoelace formula."""
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
    avg_lat = sum(point[1] for point in ring) / n
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(avg_lat))
    return round(area * km_per_deg_lat * km_per_deg_lon, 2)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors and return a clean JSON response."""
    logger.exception("Unhandled error while processing %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Internal server error."},
    )


# ---------------------------------------------------------------------------
# Frontend static files (single-container deployments)
# ---------------------------------------------------------------------------

_FRONTEND_DIST_CANDIDATES = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path(__file__).resolve().parent.parent / "frontend" / "dist",
)
frontend_dist: Path | None = next(
    (path for path in _FRONTEND_DIST_CANDIDATES if path.is_dir()), None
)

if frontend_dist is not None:
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
async def serve_frontend(full_path: str) -> FileResponse | JSONResponse:
    """Serve the built React SPA, or a JSON 404 for unknown API routes."""
    if full_path.startswith(("api/", "ws/")):
        return JSONResponse(
            status_code=404,
            content={"status": "error", "detail": "Not found"},
        )

    if frontend_dist is not None:
        requested = (frontend_dist / full_path).resolve()
        try:
            requested.relative_to(frontend_dist.resolve())  # noqa: ASYNC240
        except ValueError:
            return JSONResponse(
                status_code=404, content={"status": "error", "detail": "Not found"}
            )
        if requested.is_file():
            return FileResponse(str(requested))
        index = frontend_dist / "index.html"
        if index.is_file():
            return FileResponse(str(index))

    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "detail": "Frontend is not built. Run `npm run build` in frontend/.",
        },
    )
