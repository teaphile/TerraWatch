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
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from cachetools import TTLCache

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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

    def get(self, key: str) -> Optional[Any]:
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
        return f"{prefix}:{hash_val}"

    # ---- L2 disk persistence (SQLite) ----

    def _disk_get(self, key: str) -> Optional[Any]:
        """Read from SQLite L2 cache."""
        try:
            from app.database import engine
            import sqlite3

            # Use sync connection for cache (fast, single-row reads)
            db_url = str(engine.url)
            db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.execute(
                    "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                if row:
                    value_str, expires_str = row
                    expires = datetime.fromisoformat(expires_str)
                    if expires > datetime.now(timezone.utc):
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
        """Write to SQLite L2 cache."""
        try:
            from app.database import engine
            import sqlite3

            db_url = str(engine.url)
            db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            expires = datetime.now(timezone.utc) + timedelta(seconds=self._ttl)
            value_str = json.dumps(value, default=str)

            conn = sqlite3.connect(db_path)
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
        """Delete from SQLite L2 cache."""
        try:
            from app.database import engine
            import sqlite3

            db_url = str(engine.url)
            db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Disk cache delete failed: {e}")


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
