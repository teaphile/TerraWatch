"""
Tests for soil analysis models.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.soil_model import SoilPredictionModel, get_soil_model
from app.models.erosion_model import ErosionModel, get_erosion_model


class TestSoilModel:
    """Test soil property prediction model."""

    def setup_method(self):
        self.model = get_soil_model()

    def test_predict_returns_all_properties(self):
        result = self.model.predict(
            latitude=40.0, longitude=-95.0, elevation=300, slope=5,
            ndvi=0.6, land_cover="cropland",
        )
        assert "ph" in result
        assert "organic_carbon_pct" in result
        assert "nitrogen_pct" in result
        assert "texture" in result
        assert "bulk_density_gcm3" in result
        assert "cec_cmolkg" in result
        assert "moisture_pct" in result

    def test_ph_in_valid_range(self):
        result = self.model.predict(
            latitude=40.0, longitude=-95.0, elevation=300, slope=5,
            ndvi=0.6, land_cover="cropland",
        )
        assert 3.0 <= result["ph"]["value"] <= 10.0

    def test_organic_carbon_positive(self):
        result = self.model.predict(
            latitude=40.0, longitude=-95.0, elevation=300, slope=5,
            ndvi=0.6, land_cover="forest",
        )
        assert result["organic_carbon_pct"]["value"] > 0

    def test_texture_sums_to_100(self):
        result = self.model.predict(
            latitude=40.0, longitude=-95.0, elevation=300, slope=5,
            ndvi=0.6, land_cover="cropland",
        )
        tex = result["texture"]
        total = tex["sand_pct"] + tex["silt_pct"] + tex["clay_pct"]
        assert abs(total - 100.0) < 1.0, f"Texture sum = {total}, expected ~100"

    def test_texture_classification_present(self):
        result = self.model.predict(
            latitude=40.0, longitude=-95.0, elevation=300, slope=5,
            ndvi=0.6, land_cover="cropland",
        )
        assert len(result["texture"]["classification"]) > 0

    def test_different_inputs_give_different_results(self):
        forest = self.model.predict(
            latitude=5.0, longitude=30.0, elevation=200, slope=3,
            ndvi=0.7, land_cover="forest",
        )
        bare = self.model.predict(
            latitude=25.0, longitude=30.0, elevation=500, slope=3,
            ndvi=0.1, land_cover="bare",
        )
        assert forest["ph"]["value"] != bare["ph"]["value"] or \
               forest["organic_carbon_pct"]["value"] != bare["organic_carbon_pct"]["value"]

    def test_moisture_non_negative(self):
        result = self.model.predict(
            latitude=40.0, longitude=-95.0, elevation=300, slope=5,
            ndvi=0.6, land_cover="cropland",
        )
        assert result["moisture_pct"]["value"] >= 0

    def test_singleton(self):
        m1 = get_soil_model()
        m2 = get_soil_model()
        assert m1 is m2


class TestErosionModel:
    """Test RUSLE erosion model."""

    def setup_method(self):
        self.model = get_erosion_model()

    def test_calculate_returns_all_factors(self):
        result = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=2.5, slope_pct=17.6, slope_length_m=100,
            land_cover="cropland", ndvi=0.5, conservation_practice="contour_farming",
        )
        assert hasattr(result, "soil_loss_tons_ha_yr")
        assert hasattr(result, "risk_level")
        assert hasattr(result, "R")
        assert hasattr(result, "K")
        assert hasattr(result, "LS")
        assert hasattr(result, "C")
        assert hasattr(result, "P")

    def test_erosion_non_negative(self):
        result = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=2.5, slope_pct=17.6, slope_length_m=100,
            land_cover="cropland", ndvi=0.5,
        )
        assert result.soil_loss_tons_ha_yr >= 0

    def test_steep_slope_higher_erosion(self):
        flat = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=2.5, slope_pct=3.5, slope_length_m=100,
            land_cover="cropland", ndvi=0.5,
        )
        steep = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=2.5, slope_pct=57.7, slope_length_m=100,
            land_cover="cropland", ndvi=0.5,
        )
        assert steep.soil_loss_tons_ha_yr > flat.soil_loss_tons_ha_yr

    def test_risk_level_valid(self):
        result = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=2.5, slope_pct=17.6, slope_length_m=100,
            land_cover="cropland", ndvi=0.5,
        )
        valid_levels = {"Very Low", "Low", "Moderate", "High", "Very High", "Severe"}
        assert result.risk_level in valid_levels

    def test_forest_lower_erosion_than_bare(self):
        forest = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=3.0, slope_pct=17.6, slope_length_m=100,
            land_cover="forest", ndvi=0.8,
        )
        bare = self.model.calculate(
            annual_precip_mm=800, sand_pct=40, silt_pct=35, clay_pct=25,
            organic_carbon_pct=3.0, slope_pct=17.6, slope_length_m=100,
            land_cover="bare", ndvi=0.05,
        )
        assert forest.soil_loss_tons_ha_yr < bare.soil_loss_tons_ha_yr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
