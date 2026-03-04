"""Configuration and environment variables for TerraWatch."""

from __future__ import annotations

import logging
import os
import secrets
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _default_secret_key() -> str:
    """Generate a random secret key if none is provided via env."""
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "TerraWatch"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./terrawatch.db"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,https://*.hf.space"

    # API Keys — auto-generated if not set; override via env for production
    API_SECRET_KEY: str = ""
    FIRMS_MAP_KEY: str = ""  # NASA FIRMS MAP_KEY (get free at firms.modaps.eosdis.nasa.gov)
    OPENWEATHER_API_KEY: str = ""
    MAPBOX_TOKEN: str = ""

    # Feature flags
    OPEN_METEO_ENABLED: bool = True
    USGS_API_ENABLED: bool = True

    # Cache
    CACHE_TTL_SECONDS: int = 3600
    CACHE_MAX_SIZE: int = 1000
    CACHE_PERSIST: bool = True  # Enable disk-backed L2 cache (SQLite)

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Data fetching intervals (seconds)
    EARTHQUAKE_FETCH_INTERVAL: int = 300
    WEATHER_FETCH_INTERVAL: int = 1800
    SATELLITE_FETCH_INTERVAL: int = 21600

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()

    # Auto-generate secret key if not explicitly provided
    if not settings.API_SECRET_KEY:
        settings.API_SECRET_KEY = _default_secret_key()
        logger.warning(
            "API_SECRET_KEY not set — using auto-generated key. "
            "Set it in .env or as an environment variable for production!"
        )

    # Warn about wildcard CORS in non-debug mode
    if settings.CORS_ORIGINS.strip() == "*" and not settings.DEBUG:
        logger.warning(
            "CORS_ORIGINS is set to '*' in non-debug mode. "
            "This allows any origin to make requests. "
            "Set specific origins for production use."
        )

    return settings
