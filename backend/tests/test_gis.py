"""
Tests for GIS utility functions.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.geo_utils import haversine, validate_coordinates, deg_to_dms


class TestHaversine:
    def test_same_point(self):
        d = haversine(40.0, -95.0, 40.0, -95.0)
        assert d == 0.0

    def test_known_distance(self):
        # New York to London ≈ 5,570 km
        d = haversine(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5500 < d < 5700

    def test_antipodal(self):
        d = haversine(0, 0, 0, 180)
        assert 20000 < d < 20100

    def test_symmetry(self):
        d1 = haversine(30, 60, 45, 90)
        d2 = haversine(45, 90, 30, 60)
        assert abs(d1 - d2) < 0.01


class TestValidateCoordinates:
    def test_valid_coords(self):
        valid, msg = validate_coordinates(45.0, -90.0)
        assert valid is True

    def test_boundary_coords(self):
        valid, _ = validate_coordinates(90.0, 180.0)
        assert valid is True
        valid, _ = validate_coordinates(-90.0, -180.0)
        assert valid is True

    def test_invalid_latitude(self):
        valid, _ = validate_coordinates(91.0, 0.0)
        assert valid is False

    def test_invalid_longitude(self):
        valid, _ = validate_coordinates(0.0, 181.0)
        assert valid is False


class TestDegToDms:
    def test_positive_degrees(self):
        result = deg_to_dms(45.5)
        assert "45" in result
        assert "°" in result

    def test_zero(self):
        result = deg_to_dms(0.0)
        assert "0" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
