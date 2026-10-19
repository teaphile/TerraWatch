"""Rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    Limits requests per minute per client IP address.
    """

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._clients: dict[str, list] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        """Check rate limit before processing request."""
        # Static assets and the SPA shell are cheap to serve and are
        # requested in bursts; only /api/ needs protection.
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Opportunistically prune idle clients so the bookkeeping dict
        # cannot grow without bound.
        if len(self._clients) > 1000:
            for address in [
                address
                for address, stamps in self._clients.items()
                if not stamps or now - stamps[-1] > 60
            ]:
                self._clients.pop(address, None)

        # Clean old entries
        self._clients[client_ip] = [
            t for t in self._clients[client_ip] if now - t < 60
        ]

        if len(self._clients[client_ip]) >= self.rpm:
            response = JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "detail": f"Rate limit exceeded. Max {self.rpm} requests per minute.",
                },
            )
            response.headers["Retry-After"] = "60"
            response.headers["X-RateLimit-Limit"] = str(self.rpm)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        self._clients[client_ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(
            self.rpm - len(self._clients[client_ip])
        )
        return response
