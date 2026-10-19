"""Optional API key authentication middleware."""

from __future__ import annotations

import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

settings = get_settings()

# Paths that never require authentication.
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/info",
    "/api/v1/data-quality",
}

# Path prefixes that are always public (documentation and websockets).
PUBLIC_PREFIXES = ("/docs", "/redoc", "/assets", "/ws/")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key authentication middleware.

    Authentication is enforced only when ``API_AUTH_ENABLED`` is true and
    ``API_SECRET_KEY`` is non-empty. When disabled (the default) all
    requests are allowed, which keeps the public demo usable.
    """

    async def dispatch(self, request: Request, call_next):
        """Validate the API key for protected requests."""
        path = request.url.path

        if (
            path in PUBLIC_PATHS
            or path.startswith(PUBLIC_PREFIXES)
            or request.method == "OPTIONS"
        ):
            return await call_next(request)

        if not settings.API_AUTH_ENABLED or not settings.API_SECRET_KEY:
            return await call_next(request)

        api_key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "detail": (
                        "API key required. Pass it via the X-API-Key header "
                        "or the api_key query parameter."
                    ),
                },
            )

        if not secrets.compare_digest(api_key, settings.API_SECRET_KEY):
            return JSONResponse(
                status_code=403,
                content={"status": "error", "detail": "Invalid API key."},
            )

        return await call_next(request)
