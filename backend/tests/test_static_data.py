"""Tests for the bundled elevation and climate datasets.

These datasets back every fallback, so a bad resample or a wrong grid
orientation would silently produce nonsense for offline deployments.
"""

import json

import app.services.weather_service as weather_service
import numpy as np
import pytest


def test_elevation_grid_shape_and_dtype():
    grid = weather_service._load_elevation_grid()
    assert grid is not None
    assert grid.shape == (1081, 2161)
    assert grid.dtype == np.int16


@pytest.mark.parametrize(
    ("name", "lat", "lon", "expected", "tolerance"),
    [
        ("Delhi", 28.6139, 77.2090, 217, 80),
        ("London", 51.5074, -0.1278, 26, 50),
        ("Singapore", 1.3521, 103.8198, 26, 60),
        ("New York", 40.7128, -74.0060, 12, 60),
        ("Sydney", -33.8688, 151.2093, 28, 80),
        ("Denver", 39.7392, -104.9903, 1609, 400),
    ],
)
def test_elevation_samples_match_known_cities(name, lat, lon, expected, tolerance):
    value = weather_service._sample_elevation(lat, lon)
    assert value is not None, name
    assert abs(value - expected) <= tolerance, f"{name}: {value} vs {expected}"


def test_elevation_is_never_negative_over_sea_level():
    # Ocean points are clamped to sea level for the land analysis fallback.
    for lat, lon in [(0.0, -140.0), (30.0, -40.0), (-45.0, 160.0)]:
        assert weather_service._sample_elevation(lat, lon) == 0.0


@pytest.mark.parametrize(
    ("name", "lat", "lon", "climate_class", "temp_range", "precip_range"),
    [
        ("Delhi", 28.6139, 77.2090, "BSh", (20, 30), (200, 800)),
        ("London", 51.5074, -0.1278, "Cfb", (8, 15), (600, 1200)),
        ("Singapore", 1.3521, 103.8198, "Af", (24, 29), (1800, 3200)),
    ],
)
def test_koppen_class_lookup(
    name, lat, lon, climate_class, temp_range, precip_range
):
    climate = weather_service._interpolate_climate(lat, lon)
    assert climate is not None, name
    assert climate["_class"] == climate_class
    assert temp_range[0] <= climate["t"] <= temp_range[1]
    assert precip_range[0] <= climate["p"] <= precip_range[1]


def test_koppen_grid_covers_land():
    grid = weather_service._load_koppen_grid()
    assert grid
    classes = grid["classes"]
    coverage = float((classes != weather_service._KOPPEN_NODATA).mean())
    # Land is roughly 29 % of the globe; Antarctica and islands push this up.
    assert 0.25 <= coverage <= 0.45


def test_climate_class_normals_metadata():
    path = weather_service.STATIC_DATA_DIR / "climate_class_normals.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "classes" in payload
    assert len(payload["classes"]) >= 25
    for values in payload["classes"].values():
        assert -20 <= values["mean_annual_temp_c"] <= 35
        assert 50 <= values["mean_annual_precip_mm"] <= 4000
