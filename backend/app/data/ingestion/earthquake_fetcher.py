"""USGS Earthquake data fetcher.

Fetches real-time earthquake data from USGS Earthquake Hazards API
and generates alerts for significant seismic events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.services.alert_service import get_alert_service
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

USGS_API_BASE = "https://earthquake.usgs.gov/fdsnws/event/1"


class EarthquakeFetcher:
    """Fetches earthquake data from USGS API.

    Polls the USGS FDSN web service for recent earthquakes
    and creates alerts for significant events.
    """

    def __init__(self) -> None:
        """Initialize earthquake fetcher."""
        self._client: Optional[httpx.AsyncClient] = None
        self._cache = CacheService(maxsize=100, ttl=300)
        self._seen_events: set = set()
        self._alert_service = get_alert_service()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def fetch_recent(
        self,
        days: int = 1,
        min_magnitude: float = 2.5,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch recent earthquakes from USGS.

        Args:
            days: Number of days to look back.
            min_magnitude: Minimum magnitude threshold.
            limit: Maximum number of results.

        Returns:
            List of earthquake event dictionaries.
        """
        cache_key = f"eq_{days}_{min_magnitude}_{limit}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            client = await self._get_client()
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)

            resp = await client.get(
                f"{USGS_API_BASE}/query",
                params={
                    "format": "geojson",
                    "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                    "minmagnitude": min_magnitude,
                    "limit": limit,
                    "orderby": "time",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            events = []
            for feature in data.get("features", []):
                event = self._parse_event(feature)
                if event:
                    events.append(event)
                    self._check_alert(event)

            self._cache.set(cache_key, events)
            return events

        except Exception as e:
            logger.error(f"USGS API fetch failed: {e}")
            return []

    async def fetch_by_region(
        self,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        days: int = 7,
        min_magnitude: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Fetch earthquakes within a bounding box.

        Args:
            min_lat: Minimum latitude.
            max_lat: Maximum latitude.
            min_lon: Minimum longitude.
            max_lon: Maximum longitude.
            days: Number of days to look back.
            min_magnitude: Minimum magnitude.

        Returns:
            List of earthquake events in the region.
        """
        try:
            client = await self._get_client()
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)

            resp = await client.get(
                f"{USGS_API_BASE}/query",
                params={
                    "format": "geojson",
                    "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
                    "minlatitude": min_lat,
                    "maxlatitude": max_lat,
                    "minlongitude": min_lon,
                    "maxlongitude": max_lon,
                    "minmagnitude": min_magnitude,
                    "orderby": "time",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            return [self._parse_event(f) for f in data.get("features", []) if f]

        except Exception as e:
            logger.error(f"USGS region fetch failed: {e}")
            return []

    def _parse_event(self, feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse USGS GeoJSON feature into event dict."""
        try:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [0, 0, 0])

            event_time = props.get("time")
            if event_time:
                event_time = datetime.fromtimestamp(
                    event_time / 1000, tz=timezone.utc
                ).isoformat()

            return {
                "event_id": feature.get("id", ""),
                "latitude": coords[1],
                "longitude": coords[0],
                "depth_km": coords[2] if len(coords) > 2 else 0,
                "magnitude": props.get("mag", 0),
                "magnitude_type": props.get("magType", ""),
                "place": props.get("place", ""),
                "event_time": event_time,
                "url": props.get("url", ""),
                "felt": props.get("felt"),
                "tsunami": bool(props.get("tsunami", 0)),
                "alert_level": props.get("alert"),
                "significance": props.get("sig", 0),
            }
        except Exception as e:
            logger.warning(f"Failed to parse earthquake event: {e}")
            return None

    def _check_alert(self, event: Dict[str, Any]) -> None:
        """Create alert for significant earthquakes."""
        event_id = event.get("event_id", "")
        if event_id in self._seen_events:
            return
        self._seen_events.add(event_id)

        # Limit seen events set size
        if len(self._seen_events) > 1000:
            self._seen_events = set(list(self._seen_events)[-500:])

        magnitude = event.get("magnitude", 0)
        if magnitude >= 4.0:
            if magnitude >= 7.0:
                severity = "critical"
            elif magnitude >= 6.0:
                severity = "warning"
            elif magnitude >= 5.0:
                severity = "watch"
            else:
                severity = "advisory"

            self._alert_service.create_alert(
                alert_type="earthquake",
                severity=severity,
                title=f"M{magnitude} Earthquake - {event.get('place', 'Unknown')}",
                description=(
                    f"Magnitude {magnitude} earthquake detected at "
                    f"depth {event.get('depth_km', 0):.1f}km. "
                    f"{'Tsunami warning issued.' if event.get('tsunami') else ''}"
                ),
                latitude=event.get("latitude"),
                longitude=event.get("longitude"),
                radius_km=magnitude * 50,
                data=event,
                ttl_hours=48,
            )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_fetcher_instance: Optional[EarthquakeFetcher] = None


def get_earthquake_fetcher() -> EarthquakeFetcher:
    """Get or create singleton earthquake fetcher."""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = EarthquakeFetcher()
    return _fetcher_instance
