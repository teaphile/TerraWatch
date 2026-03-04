"""API key authentication middleware."""

from __future__ import annotations

import secrets

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

settings = get_settings()

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/", "/docs", "/redoc", "/openapi.json",
    "/api/v1/health", "/api/v1/info", "/api/v1/data-quality",
    "/ws/alerts",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key authentication middleware.

    Auth is enforced when API_SECRET_KEY is set to a non-empty value
    via environment variable. Public paths are always open.
    In development (no key set), all requests are allowed.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and check API key if required."""
        path = request.url.path

        # Skip auth for public paths
        if (path in PUBLIC_PATHS or
            path.startswith("/docs") or
            path.startswith("/redoc")):
            return await call_next(request)

        # If no secret key is configured, run in open/development mode
        if not settings.API_SECRET_KEY:
            return await call_next(request)

        # Check for API key in header or query parameter
        api_key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required. Pass via X-API-Key header or api_key query parameter.",
            )

        if not secrets.compare_digest(api_key, settings.API_SECRET_KEY):
            raise HTTPException(
                status_code=403,
                detail="Invalid API key.",
            )

        return await call_next(request)
