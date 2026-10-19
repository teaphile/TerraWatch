"""Configuration and environment variables for TerraWatch."""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden with environment variables or a
    ``.env`` file placed in the backend working directory. The defaults
    are safe for local development and require no API keys.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "TerraWatch"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./terrawatch.db"

    # CORS. Comma-separated list of exact origins; ``*`` wildcards are
    # supported inside a hostname (for example ``https://*.hf.space``).
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:4173,"
        "http://127.0.0.1:5173,http://127.0.0.1:4173,https://*.hf.space"
    )

    # Authentication. Disabled by default; enable for a private deployment.
    API_AUTH_ENABLED: bool = False
    API_SECRET_KEY: str = ""

    # Optional third-party API keys
    FIRMS_MAP_KEY: str = ""  # NASA FIRMS MAP_KEY (firms.modaps.eosdis.nasa.gov)

    # Feature flags
    OPEN_METEO_ENABLED: bool = True
    USGS_API_ENABLED: bool = True

    # Cache
    CACHE_MAX_SIZE: int = 1000
    CACHE_PERSIST: bool = True  # SQLite-backed L2 cache survives restarts

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Upstream HTTP timeouts (seconds)
    HTTP_CONNECT_TIMEOUT: float = 5.0
    HTTP_READ_TIMEOUT: float = 12.0

    # Background polling interval (seconds)
    EARTHQUAKE_FETCH_INTERVAL: int = 300

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins without wildcard patterns."""
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip() and "*" not in origin
        ]

    @property
    def cors_origin_regex(self) -> str | None:
        """Build a regex for wildcard CORS origins.

        Starlette's CORSMiddleware only understands exact origins and
        ``*``. Patterns such as ``https://*.hf.space`` therefore need to
        be translated into a regular expression.
        """
        patterns = [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if "*" in origin
        ]
        if not patterns:
            return None
        return "|".join(
            "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
            for pattern in patterns
        )


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    settings = Settings()

    if settings.CORS_ORIGINS.strip() == "*" and not settings.DEBUG:
        import logging

        logging.getLogger(__name__).warning(
            "CORS_ORIGINS is set to '*' in non-debug mode. "
            "This allows any origin to make requests. "
            "Set specific origins for production use."
        )

    if settings.API_AUTH_ENABLED and not settings.API_SECRET_KEY:
        import logging

        logging.getLogger(__name__).warning(
            "API_AUTH_ENABLED is true but API_SECRET_KEY is empty; "
            "authentication middleware will stay disabled."
        )

    return settings
