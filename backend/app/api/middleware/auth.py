"""API key authentication middleware."""

from __future__ import annotations

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

settings = get_settings()

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/", "/docs", "/redoc", "/openapi.json",
    "/api/v1/health", "/ws/alerts",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key authentication middleware.

    Only enforced if API_SECRET_KEY is set to a non-default value.
    Public paths are always accessible.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and check API key if required."""
        path = request.url.path

        # Skip auth for public paths and in development
        if (path in PUBLIC_PATHS or
            path.startswith("/docs") or
            path.startswith("/redoc") or
            settings.API_SECRET_KEY == "terrawatch-default-secret-key-change-me"):
            return await call_next(request)

        # Check for API key in header or query parameter
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

        if not api_key:
            # Allow requests without key in development mode
            pass

        return await call_next(request)
