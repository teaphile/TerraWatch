"""
Tests for disaster risk models.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.landslide_model import LandslideModel, get_landslide_model
from app.models.flood_model import FloodModel, get_flood_model
from app.models.liquefaction_model import LiquefactionModel, get_liquefaction_model
from app.models.fire_model import FireModel, get_fire_model


class TestLandslideModel:
    """Test landslide susceptibility model."""

    def setup_method(self):
        self.model = get_landslide_model()

    def test_predict_returns_required_fields(self):
        result = self.model.predict(
            latitude=35.0, longitude=139.0,
            slope=25, rainfall_mm=200, soil_type="clay",
            land_cover="forest", elevation=1500, ndvi=0.6,
            soil_moisture=40, lithology="sedimentary",
            distance_to_fault_km=5,
        )
        assert "probability" in result
        assert "risk_level" in result
        assert 0 <= result["probability"] <= 1

    def test_steep_slope_higher_risk(self):
        flat = self.model.predict(
            latitude=35.0, longitude=139.0,
            slope=3, rainfall_mm=100, soil_type="sand",
            land_cover="grassland", elevation=200, ndvi=0.5,
            soil_moisture=30,
        )
        steep = self.model.predict(
            latitude=35.0, longitude=139.0,
            slope=45, rainfall_mm=100, soil_type="sand",
            land_cover="grassland", elevation=200, ndvi=0.5,
            soil_moisture=30,
        )
        assert steep["probability"] > flat["probability"]

    def test_heavy_rain_higher_risk(self):
        dry = self.model.predict(
            latitude=35.0, longitude=139.0,
            slope=20, rainfall_mm=10, soil_type="clay",
            land_cover="forest", elevation=800, ndvi=0.5,
            soil_moisture=20,
        )
        wet = self.model.predict(
            latitude=35.0, longitude=139.0,
            slope=20, rainfall_mm=400, soil_type="clay",
            land_cover="forest", elevation=800, ndvi=0.5,
            soil_moisture=80,
        )
        assert wet["probability"] > dry["probability"]


class TestFloodModel:
    """Test flood risk model."""

    def setup_method(self):
        self.model = get_flood_model()

    def test_predict_returns_required_fields(self):
        result = self.model.predict(
            latitude=30.0, longitude=-90.0,
            elevation=50, slope=2, rainfall_mm_24h=150,
            soil_type="clay", land_cover="urban",
            distance_to_river_km=0.5, drainage_density=3.0,
            soil_moisture=60, ndvi=0.2,
        )
        assert "probability" in result
        assert "risk_level" in result
        assert "return_period_years" in result
        assert "max_inundation_depth_m" in result

    def test_low_elevation_higher_flood_risk(self):
        high = self.model.predict(
            latitude=30.0, longitude=-90.0,
            elevation=500, slope=15, rainfall_mm_24h=100,
            soil_type="sand", land_cover="forest",
            distance_to_river_km=10, drainage_density=1.0,
            soil_moisture=30, ndvi=0.7,
        )
        low = self.model.predict(
            latitude=30.0, longitude=-90.0,
            elevation=10, slope=1, rainfall_mm_24h=100,
            soil_type="clay", land_cover="urban",
            distance_to_river_km=0.1, drainage_density=3.0,
            soil_moisture=60, ndvi=0.1,
        )
        assert low["probability"] > high["probability"]


class TestLiquefactionModel:
    """Test liquefaction susceptibility model."""

    def setup_method(self):
        self.model = get_liquefaction_model()

    def test_predict_returns_required_fields(self):
        result = self.model.predict(
            sand_pct=70, silt_pct=20, clay_pct=10,
            groundwater_depth_m=2.0, bulk_density=1.6,
            soil_moisture=40,
        )
        assert "susceptibility" in result
        assert "probability_given_m7" in result

    def test_sandy_soil_higher_susceptibility(self):
        sandy = self.model.predict(
            sand_pct=90, silt_pct=5, clay_pct=5,
            groundwater_depth_m=1.0, bulk_density=1.5,
            soil_moisture=50,
        )
        clayey = self.model.predict(
            sand_pct=10, silt_pct=30, clay_pct=60,
            groundwater_depth_m=5.0, bulk_density=1.8,
            soil_moisture=30,
        )
        assert sandy["probability_given_m7"] > clayey["probability_given_m7"]


class TestFireModel:
    """Test wildfire risk model."""

    def setup_method(self):
        self.model = get_fire_model()

    def test_predict_returns_required_fields(self):
        result = self.model.predict(
            latitude=35.0, longitude=-118.0,
            temperature_c=35, humidity_pct=15, wind_speed_kmh=30,
            ndvi=0.3, soil_moisture=10,
            rainfall_last_7d_mm=0, slope=10,
            elevation=300, land_cover="grassland",
            days_since_rain=20,
        )
        assert "probability" in result
        assert "risk_level" in result
        assert "vegetation_dryness_index" in result

    def test_hot_dry_windy_higher_risk(self):
        mild = self.model.predict(
            latitude=45.0, longitude=-118.0,
            temperature_c=15, humidity_pct=80, wind_speed_kmh=5,
            ndvi=0.7, soil_moisture=50,
            rainfall_last_7d_mm=30, slope=5,
            elevation=300, land_cover="forest",
            days_since_rain=1,
        )
        extreme = self.model.predict(
            latitude=35.0, longitude=-118.0,
            temperature_c=42, humidity_pct=8, wind_speed_kmh=50,
            ndvi=0.2, soil_moisture=5,
            rainfall_last_7d_mm=0, slope=15,
            elevation=300, land_cover="grassland",
            days_since_rain=45,
        )
        assert extreme["probability"] > mild["probability"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
