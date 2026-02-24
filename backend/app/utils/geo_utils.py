"""Geospatial utility functions."""
from __future__ import annotations
import math
from typing import Tuple


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def validate_coordinates(lat: float, lon: float) -> Tuple[bool, str]:
    """Validate latitude and longitude values."""
    if not -90 <= lat <= 90:
        return False, f"Latitude {lat} out of range [-90, 90]"
    if not -180 <= lon <= 180:
        return False, f"Longitude {lon} out of range [-180, 180]"
    return True, "Valid"


def deg_to_dms(deg: float) -> str:
    """Convert decimal degrees to DMS string."""
    d = int(deg)
    m = int((abs(deg) - abs(d)) * 60)
    s = round((abs(deg) - abs(d) - m / 60) * 3600, 1)
    return f"{d}°{m}'{s}\""
