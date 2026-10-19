"""Cache service for TerraWatch.

Provides TTL-based caching with optional disk-backed L2 persistence
using SQLite so that cached API responses survive container restarts.

Architecture:
  L1 = in-memory TTLCache (fast, lost on restart)
  L2 = SQLite cache_entries table (slower, persists across restarts)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from cachetools import TTLCache

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Bump when the shape of cached payloads changes so stale entries written by
# an older build are never served.
CACHE_VERSION = 3


class CacheService:
    """In-memory TTL cache with optional SQLite L2 persistence.

    L1 (memory) is always active. L2 (disk) is enabled when
    settings.CACHE_PERSIST is True.
    """

    def __init__(
        self,
        maxsize: int = 1000,
        ttl: int = 3600,
        persist: bool = True,
    ) -> None:
        """Initialize cache with size and TTL limits."""
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._ttl = ttl
        self._persist = persist and settings.CACHE_PERSIST
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache (L1 first, then L2 disk).

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        # L1: in-memory
        value = self._cache.get(key)
        if value is not None:
            self._hits += 1
            return value

        # L2: disk
        if self._persist:
            disk_val = self._disk_get(key)
            if disk_val is not None:
                # Promote to L1
                self._cache[key] = disk_val
                self._hits += 1
                return disk_val

        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache (both L1 and L2).

        Args:
            key: Cache key.
            value: Value to cache.
        """
        self._cache[key] = value

        if self._persist:
            self._disk_set(key, value)

    def delete(self, key: str) -> None:
        """Remove value from cache."""
        self._cache.pop(key, None)
        if self._persist:
            self._disk_delete(key)

    def clear(self) -> None:
        """Clear both the memory cache and the persistent cache."""
        self._cache.clear()
        if self._persist:
            self._disk_clear()

    def purge_expired(self) -> None:
        """Remove expired rows from the persistent cache."""
        if self._persist:
            self._disk_purge_expired()

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(
                self._hits / max(1, self._hits + self._misses) * 100, 1
            ),
            "persist_enabled": self._persist,
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
        return f"v{CACHE_VERSION}:{prefix}:{hash_val}"

    # ---- L2 disk persistence (SQLite) ----

    @staticmethod
    def _sqlite_path() -> str:
        """Return the on-disk SQLite database path."""
        from app.database import engine

        database = engine.url.database
        if not database:
            raise RuntimeError("Persistent cache requires a file-based SQLite URL")
        return database

    def _disk_get(self, key: str) -> Any | None:
        """Read one value from the SQLite L2 cache."""
        try:
            import sqlite3

            conn = sqlite3.connect(self._sqlite_path(), timeout=5)
            try:
                cursor = conn.execute(
                    "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                if row:
                    value_str, expires_str = row
                    expires = datetime.fromisoformat(expires_str)
                    if expires > datetime.now(UTC):
                        return json.loads(value_str)
                    else:
                        # Expired — clean up
                        conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                        conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Disk cache get failed: {e}")
        return None

    def _disk_set(self, key: str, value: Any) -> None:
        """Write one value to the SQLite L2 cache."""
        try:
            import sqlite3

            expires = datetime.now(UTC) + timedelta(seconds=self._ttl)
            value_str = json.dumps(value, default=str)

            conn = sqlite3.connect(self._sqlite_path(), timeout=5)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cache_entries (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, value_str, expires.isoformat()),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Disk cache set failed: {e}")

    def _disk_delete(self, key: str) -> None:
        """Delete one key from the SQLite L2 cache."""
        try:
            import sqlite3

            conn = sqlite3.connect(self._sqlite_path(), timeout=5)
            try:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Disk cache delete failed: {e}")

    def _disk_clear(self) -> None:
        """Delete every entry from the SQLite L2 cache."""
        try:
            import sqlite3

            conn = sqlite3.connect(self._sqlite_path(), timeout=5)
            try:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Disk cache clear failed: {e}")

    def _disk_purge_expired(self) -> None:
        """Delete expired entries from the SQLite L2 cache."""
        try:
            import sqlite3

            conn = sqlite3.connect(self._sqlite_path(), timeout=5)
            try:
                conn.execute(
                    "DELETE FROM cache_entries WHERE expires_at < ?",
                    (datetime.now(UTC).isoformat(),),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Disk cache purge failed: {e}")


# Singleton instances
_soil_cache: CacheService | None = None
_risk_cache: CacheService | None = None
_weather_cache: CacheService | None = None
_climate_cache: CacheService | None = None
_elevation_cache: CacheService | None = None
_precipitation_cache: CacheService | None = None
_moisture_cache: CacheService | None = None


def get_soil_cache() -> CacheService:
    """Get soil analysis cache (1h TTL)."""
    global _soil_cache
    if _soil_cache is None:
        _soil_cache = CacheService(maxsize=settings.CACHE_MAX_SIZE, ttl=3600)
    return _soil_cache


def get_risk_cache() -> CacheService:
    """Get risk assessment cache (30min TTL)."""
    global _risk_cache
    if _risk_cache is None:
        _risk_cache = CacheService(maxsize=settings.CACHE_MAX_SIZE, ttl=1800)
    return _risk_cache


def get_weather_cache() -> CacheService:
    """Get weather data cache (15min TTL)."""
    global _weather_cache
    if _weather_cache is None:
        _weather_cache = CacheService(
        maxsize=min(settings.CACHE_MAX_SIZE, 500), ttl=900
    )
    return _weather_cache


def get_climate_cache() -> CacheService:
    """Get climate-normals cache (7 day TTL)."""
    global _climate_cache
    if _climate_cache is None:
        _climate_cache = CacheService(maxsize=200, ttl=7 * 24 * 3600)
    return _climate_cache


def get_elevation_cache() -> CacheService:
    """Get elevation cache (30 day TTL; terrain does not move)."""
    global _elevation_cache
    if _elevation_cache is None:
        _elevation_cache = CacheService(maxsize=500, ttl=30 * 24 * 3600)
    return _elevation_cache


def get_precipitation_cache() -> CacheService:
    """Get recent-precipitation cache (30 minute TTL)."""
    global _precipitation_cache
    if _precipitation_cache is None:
        _precipitation_cache = CacheService(maxsize=300, ttl=1800)
    return _precipitation_cache


def get_moisture_cache() -> CacheService:
    """Get soil-moisture cache (1 hour TTL)."""
    global _moisture_cache
    if _moisture_cache is None:
        _moisture_cache = CacheService(maxsize=300, ttl=3600)
    return _moisture_cache
