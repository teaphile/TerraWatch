"""In-memory cache service for TerraWatch.

Provides TTL-based caching for API responses and computed results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

from cachetools import TTLCache

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheService:
    """In-memory TTL cache service.

    Provides simple key-value caching with configurable TTL
    and maximum size limits.
    """

    def __init__(
        self,
        maxsize: int = 1000,
        ttl: int = 3600,
    ) -> None:
        """Initialize cache with size and TTL limits."""
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
            return value
        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        self._cache[key] = value

    def delete(self, key: str) -> None:
        """Remove value from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    @property
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(
                self._hits / max(1, self._hits + self._misses) * 100, 1
            ),
        }

    @staticmethod
    def make_key(prefix: str, **kwargs: Any) -> str:
        """Generate cache key from prefix and parameters.

        Args:
            prefix: Key prefix (e.g., 'soil_analysis').
            **kwargs: Parameters to include in key.

        Returns:
            Deterministic cache key string.
        """
        param_str = json.dumps(kwargs, sort_keys=True, default=str)
        hash_val = hashlib.md5(param_str.encode()).hexdigest()[:12]
        return f"{prefix}:{hash_val}"


# Singleton instances
_soil_cache: Optional[CacheService] = None
_risk_cache: Optional[CacheService] = None
_weather_cache: Optional[CacheService] = None


def get_soil_cache() -> CacheService:
    """Get soil analysis cache (1h TTL)."""
    global _soil_cache
    if _soil_cache is None:
        _soil_cache = CacheService(maxsize=500, ttl=3600)
    return _soil_cache


def get_risk_cache() -> CacheService:
    """Get risk assessment cache (30min TTL)."""
    global _risk_cache
    if _risk_cache is None:
        _risk_cache = CacheService(maxsize=500, ttl=1800)
    return _risk_cache


def get_weather_cache() -> CacheService:
    """Get weather data cache (15min TTL)."""
    global _weather_cache
    if _weather_cache is None:
        _weather_cache = CacheService(maxsize=200, ttl=900)
    return _weather_cache
