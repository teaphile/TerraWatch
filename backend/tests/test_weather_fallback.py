"""Tests for improved weather fallback behavior.

Validates that the climate normals-based fallback provides realistic
values instead of hardcoded zeros.
"""

from __future__ import annotations

import pytest

from app.services.weather_service import WeatherService, _interpolate_climate


class TestWeatherFallback:
    """Test weather estimation from climate normals."""

    def setup_method(self) -> None:
        self.service = WeatherService()

    def test_tropical_precipitation_not_zero(self) -> None:
        """Tropical locations should have non-zero precipitation."""
        # Equatorial Africa (0°N, 25°E)
        result = self.service._estimate_weather(0.0, 25.0)
        assert result["precipitation_mm"] > 0, "Tropical precipitation must not be zero"
        assert result["source"] == "estimated"

    def test_tropical_temperature_warm(self) -> None:
        """Tropical locations should be warm."""
        result = self.service._estimate_weather(5.0, 10.0)
        assert result["temperature_c"] > 20, "Tropical temperature should be > 20°C"

    def test_arctic_temperature_cold(self) -> None:
        """Arctic locations should be cold."""
        result = self.service._estimate_weather(70.0, 25.0)
        assert result["temperature_c"] < 10, "Arctic temperature should be < 10°C"

    def test_sahara_low_humidity(self) -> None:
        """Saharan locations should have low humidity."""
        result = self.service._estimate_weather(25.0, 25.0)
        assert result["humidity_pct"] < 60, "Desert humidity should be low"

    def test_estimate_weather_has_warning(self) -> None:
        """Estimated weather should include a warning."""
        result = self.service._estimate_weather(45.0, -90.0)
        assert "_warning" in result
        assert "climate normals" in result["_warning"].lower()

    @pytest.mark.parametrize("city,lat,lon,expected_temp_range", [
        ("Singapore", 1.35, 103.82, (24, 32)),
        ("London", 51.51, -0.13, (5, 18)),
        ("Cairo", 30.04, 31.24, (15, 30)),
        ("Moscow", 55.75, 37.62, (-5, 15)),
        ("Buenos Aires", -34.60, -58.38, (10, 22)),
        ("Mumbai", 19.08, 72.88, (20, 32)),
        ("Sydney", -33.87, 151.21, (12, 25)),
        ("Reykjavik", 64.15, -21.94, (-5, 12)),
        ("Lima", -12.05, -77.04, (14, 26)),
        ("Tokyo", 35.68, 139.69, (8, 22)),
    ])
    def test_city_temperature_within_range(
        self, city: str, lat: float, lon: float, expected_temp_range: tuple
    ) -> None:
        """Test that estimated temperature is within ±10°C of known climate."""
        result = self.service._estimate_weather(lat, lon)
        low, high = expected_temp_range
        assert low - 10 <= result["temperature_c"] <= high + 10, (
            f"{city}: estimated {result['temperature_c']}°C not in "
            f"[{low - 10}, {high + 10}]°C"
        )


class TestClimateNormalsLookup:
    """Test the climate normals interpolation."""

    def test_interpolation_returns_data(self) -> None:
        """Climate normals interpolation should return data for land points."""
        result = _interpolate_climate(40.0, -90.0)
        assert result is not None, "Should find climate data for US Midwest"
        assert "t" in result
        assert "p" in result

    def test_tropical_high_precipitation(self) -> None:
        """Tropical regions should have high annual precipitation."""
        result = _interpolate_climate(0.0, 25.0)
        if result:
            assert result["p"] > 500, "Equatorial precipitation should be > 500mm"


class TestClimateEstimation:
    """Test climate normal estimation fallback."""

    def setup_method(self) -> None:
        self.service = WeatherService()

    def test_climate_estimate_non_zero_precip(self) -> None:
        """Climate estimate should never return 0 precipitation."""
        result = self.service._estimate_climate(5.0, 10.0)
        assert result["mean_annual_precip_mm"] > 0

    def test_climate_estimate_source_field(self) -> None:
        """Climate estimate should indicate its source."""
        result = self.service._estimate_climate(45.0, 10.0)
        assert result["source"] in ("climate_normals", "estimated")


class TestSoilMoistureEstimation:
    """Test soil moisture estimation from climate."""

    def setup_method(self) -> None:
        self.service = WeatherService()

    def test_sahara_low_moisture(self) -> None:
        """Sahara should have low soil moisture."""
        result = self.service._estimate_soil_moisture(25.0, 25.0)
        assert result["average_pct"] < 30, "Desert soil moisture should be low"

    def test_tropical_higher_moisture(self) -> None:
        """Tropical wet areas should have higher moisture."""
        result = self.service._estimate_soil_moisture(0.0, 25.0)
        assert result["average_pct"] > 15, "Tropical moisture should be moderate-high"

    def test_moisture_has_source(self) -> None:
        """Estimated moisture should indicate source."""
        result = self.service._estimate_soil_moisture(45.0, 10.0)
        assert result["source"] == "estimated_from_climate"
        assert "_warning" in result

    def test_moisture_depth_ordering(self) -> None:
        """Deeper layers should generally have equal or higher moisture."""
        result = self.service._estimate_soil_moisture(40.0, -90.0)
        assert result["shallow_1_3cm"] >= result["surface_0_1cm"] - 5
        assert result["deep_9_27cm"] >= result["shallow_1_3cm"] - 5
