"""Configuration and environment variables for TerraWatch."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


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

    # API Keys
    API_SECRET_KEY: str = "terrawatch-default-secret-key-change-me"
    OPENWEATHER_API_KEY: str = ""
    MAPBOX_TOKEN: str = ""

    # Feature flags
    OPEN_METEO_ENABLED: bool = True
    USGS_API_ENABLED: bool = True

    # Cache
    CACHE_TTL_SECONDS: int = 3600
    CACHE_MAX_SIZE: int = 1000

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
    return Settings()
