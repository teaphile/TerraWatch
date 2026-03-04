"""Tests for risk model validation.

Validates that risk models produce reasonable results for
known high-risk and low-risk locations.

Note: These are analytical models not calibrated against ground-truth data.
Tests verify directional correctness rather than exact values.
"""

from __future__ import annotations

import pytest

from app.models.landslide_model import get_landslide_model
from app.models.flood_model import get_flood_model
from app.models.fire_model import get_fire_model


@pytest.fixture
def landslide_model():
    return get_landslide_model()


@pytest.fixture
def flood_model():
    return get_flood_model()


@pytest.fixture
def fire_model():
    return get_fire_model()


class TestLandslideModelDirectional:
    """Test that landslide model responds correctly to risk factors."""

    def test_steep_wet_slope_high_risk(self, landslide_model) -> None:
        """Steep, wet slopes should produce high landslide risk."""
        result = landslide_model.predict(
            latitude=28.0,
            longitude=85.0,  # Nepal Himalaya
            elevation=2000.0,
            slope=40.0,
            soil_moisture=80.0,
            clay_pct=50.0,
            rainfall_mm=200.0,
            ndvi=0.3,
            distance_to_fault_km=5.0,
            land_cover="barren",
            lithology="metamorphic",
        )
        assert result["probability"] > 0.5, (
            f"Steep wet slope should be high risk, got {result['probability']}"
        )

    def test_flat_dry_terrain_low_risk(self, landslide_model) -> None:
        """Flat, dry terrain should produce low landslide risk."""
        result = landslide_model.predict(
            latitude=40.0,
            longitude=-100.0,  # US Great Plains
            elevation=400.0,
            slope=2.0,
            soil_moisture=15.0,
            clay_pct=15.0,
            rainfall_mm=5.0,
            ndvi=0.7,
            distance_to_fault_km=200.0,
            land_cover="cropland",
            lithology="sedimentary",
        )
        assert result["probability"] < 0.3, (
            f"Flat dry terrain should be low risk, got {result['probability']}"
        )

    def test_slope_increases_risk(self, landslide_model) -> None:
        """Increasing slope should monotonically increase risk."""
        baseline = dict(
            latitude=35.0, longitude=139.0, elevation=500.0,
            soil_moisture=40.0, clay_pct=30.0, rainfall_mm=80.0,
            ndvi=0.5, distance_to_fault_km=30.0, land_cover="forest",
        )
        result_flat = landslide_model.predict(**baseline, slope=5.0)
        result_steep = landslide_model.predict(**baseline, slope=35.0)
        assert result_steep["probability"] > result_flat["probability"]

    def test_rainfall_increases_risk(self, landslide_model) -> None:
        """Higher rainfall should increase landslide risk."""
        baseline = dict(
            latitude=35.0, longitude=139.0, elevation=500.0,
            slope=20.0, soil_moisture=40.0, clay_pct=30.0,
            ndvi=0.5, distance_to_fault_km=30.0, land_cover="forest",
        )
        result_dry = landslide_model.predict(**baseline, rainfall_mm=5.0)
        result_wet = landslide_model.predict(**baseline, rainfall_mm=200.0)
        assert result_wet["probability"] > result_dry["probability"]

    def test_output_has_required_fields(self, landslide_model) -> None:
        """Output should contain all required fields."""
        result = landslide_model.predict(latitude=35.0, longitude=139.0)
        assert "probability" in result
        assert "risk_level" in result
        assert "contributing_factors" in result
        assert 0 <= result["probability"] <= 1


class TestFloodModelDirectional:
    """Test that flood model responds correctly to risk factors."""

    def test_low_elevation_near_river_high_risk(self, flood_model) -> None:
        """Low-elevation areas near rivers with heavy rain should flood."""
        result = flood_model.predict(
            latitude=29.76,
            longitude=-95.37,  # Houston TX (flood-prone)
            elevation=15.0,
            slope=1.0,
            rainfall_mm_24h=150.0,
            rainfall_mm_annual=1300.0,
            soil_type="Clay",
            clay_pct=50.0,
            sand_pct=15.0,
            soil_moisture=85.0,
            distance_to_river_km=0.5,
            flow_accumulation=500.0,
            land_cover="urban",
            ndvi=0.2,
        )
        assert result["probability"] > 0.5, (
            f"Floodplain should be high risk, got {result['probability']}"
        )

    def test_high_elevation_dry_low_risk(self, flood_model) -> None:
        """High, dry terrain far from water should have low flood risk."""
        result = flood_model.predict(
            latitude=39.0,
            longitude=-105.5,  # Colorado mountains
            elevation=3000.0,
            slope=25.0,
            rainfall_mm_24h=5.0,
            rainfall_mm_annual=400.0,
            soil_type="Sandy Loam",
            sand_pct=60.0,
            clay_pct=10.0,
            soil_moisture=15.0,
            distance_to_river_km=20.0,
            flow_accumulation=10.0,
            land_cover="forest",
            ndvi=0.7,
        )
        assert result["probability"] < 0.3, (
            f"Mountain should be low flood risk, got {result['probability']}"
        )

    def test_rainfall_increases_flood_risk(self, flood_model) -> None:
        """Higher rainfall should increase flood risk."""
        baseline = dict(
            latitude=40.0, longitude=-90.0, elevation=200.0, slope=3.0,
            rainfall_mm_annual=800.0, soil_type="Loam", sand_pct=40.0,
            clay_pct=25.0, soil_moisture=40.0, distance_to_river_km=2.0,
            land_cover="cropland", ndvi=0.5,
        )
        result_dry = flood_model.predict(**baseline, rainfall_mm_24h=5.0)
        result_wet = flood_model.predict(**baseline, rainfall_mm_24h=150.0)
        assert result_wet["probability"] > result_dry["probability"]

    def test_output_has_required_fields(self, flood_model) -> None:
        """Output should contain all required flood-specific fields."""
        result = flood_model.predict(latitude=40.0, longitude=-90.0)
        assert "probability" in result
        assert "risk_level" in result
        assert "return_period_years" in result
        assert "max_inundation_depth_m" in result
        assert 0 <= result["probability"] <= 1


class TestFireModelDirectional:
    """Test that fire model responds correctly to risk factors."""

    def test_hot_dry_windy_high_risk(self, fire_model) -> None:
        """Hot, dry, windy conditions in fire-prone area."""
        result = fire_model.predict(
            latitude=34.0,
            longitude=-118.0,  # Southern California
            temperature_c=40.0,
            humidity_pct=10.0,
            wind_speed_kmh=50.0,
            ndvi=0.3,
            soil_moisture=5.0,
            rainfall_last_7d_mm=0.0,
            slope=15.0,
            land_cover="shrubland",
            days_since_rain=30,
        )
        assert result["probability"] > 0.4, (
            f"Fire-prone conditions should be high risk, got {result['probability']}"
        )

    def test_wet_cool_low_risk(self, fire_model) -> None:
        """Wet, cool conditions should have low fire risk."""
        result = fire_model.predict(
            latitude=55.0,
            longitude=10.0,  # Denmark
            temperature_c=5.0,
            humidity_pct=90.0,
            wind_speed_kmh=5.0,
            ndvi=0.7,
            soil_moisture=70.0,
            rainfall_last_7d_mm=50.0,
            slope=2.0,
            land_cover="cropland",
            days_since_rain=0,
        )
        assert result["probability"] < 0.3, (
            f"Wet cool conditions should be low risk, got {result['probability']}"
        )

    def test_temperature_increases_fire_risk(self, fire_model) -> None:
        """Higher temperature should increase fire risk."""
        baseline = dict(
            latitude=40.0, longitude=-120.0, humidity_pct=30.0,
            wind_speed_kmh=20.0, ndvi=0.4, soil_moisture=20.0,
            rainfall_last_7d_mm=5.0, slope=10.0, land_cover="forest",
            days_since_rain=10,
        )
        result_cool = fire_model.predict(**baseline, temperature_c=15.0)
        result_hot = fire_model.predict(**baseline, temperature_c=40.0)
        assert result_hot["probability"] > result_cool["probability"]

    def test_output_has_required_fields(self, fire_model) -> None:
        """Output should contain all required fire-specific fields."""
        result = fire_model.predict(latitude=35.0, longitude=-120.0)
        assert "probability" in result
        assert "risk_level" in result
        assert "fire_weather_index" in result
        assert "vegetation_dryness_index" in result
        assert 0 <= result["probability"] <= 1


class TestValidationStatus:
    """Test that models flag their validation status."""

    VALID_RISK_LEVELS = (
        "low", "moderate", "high", "very_high", "critical",
        "Low", "Moderate", "High", "Very High", "Critical",
    )

    def test_landslide_result_structure(self, landslide_model) -> None:
        """Landslide model should return a well-structured result."""
        result = landslide_model.predict(latitude=35.0, longitude=139.0)
        assert result["risk_level"] in self.VALID_RISK_LEVELS

    def test_flood_result_structure(self, flood_model) -> None:
        """Flood model should return a well-structured result."""
        result = flood_model.predict(latitude=35.0, longitude=139.0)
        assert result["risk_level"] in self.VALID_RISK_LEVELS

    def test_fire_result_structure(self, fire_model) -> None:
        """Fire model should return a well-structured result."""
        result = fire_model.predict(latitude=35.0, longitude=-120.0)
        assert result["risk_level"] in self.VALID_RISK_LEVELS


class TestEdgeCases:
    """Test model edge cases and boundary conditions."""

    def test_landslide_extreme_values(self, landslide_model) -> None:
        """Model should handle extreme input values gracefully."""
        result = landslide_model.predict(
            latitude=0.0, longitude=0.0, slope=90.0,
            rainfall_mm=500.0, soil_moisture=100.0,
        )
        assert 0 <= result["probability"] <= 1

    def test_flood_zero_rainfall(self, flood_model) -> None:
        """Zero rainfall should still return valid result."""
        result = flood_model.predict(
            latitude=40.0, longitude=-90.0,
            rainfall_mm_24h=0.0, rainfall_mm_annual=0.0,
        )
        assert 0 <= result["probability"] <= 1
        assert result["probability"] < 0.5  # Low risk with no rain

    def test_fire_zero_wind(self, fire_model) -> None:
        """Zero wind should still return valid result."""
        result = fire_model.predict(
            latitude=35.0, longitude=-120.0, wind_speed_kmh=0.0,
        )
        assert 0 <= result["probability"] <= 1
