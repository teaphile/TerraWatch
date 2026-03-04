"""Tests for soil model prediction accuracy.

Compares analytical predictions against known soil characteristics
for well-studied locations. Since no trained ML model is available
by default, these tests validate the analytical fallback quality.

Known ISRIC SoilGrids approximate values for reference locations
are used as ground truth (sourced from soilgrids.org).
"""

from __future__ import annotations

import pytest
import numpy as np

from app.models.soil_model import get_soil_model

# Reference data: approximate known soil properties from ISRIC SoilGrids
# Format: (name, lat, lon, elevation, mean_temp_c, precip_mm, land_cover, ndvi,
#           expected_ph_range, expected_oc_range, expected_clay_range)
REFERENCE_LOCATIONS = [
    # Humid tropical: high clay, moderate-low pH, high OC
    ("Amazon Basin", -3.0, -60.0, 50, 26, 2200, "forest", 0.8,
     (4.0, 6.5), (1.0, 5.0), (30, 70)),
    # Temperate grassland: moderate clay, neutral pH
    ("Iowa Farmland", 42.0, -93.0, 300, 10, 900, "cropland", 0.6,
     (5.5, 8.0), (1.0, 5.0), (15, 40)),
    # Arid: sandy, alkaline, low OC
    ("Sahara Edge", 25.0, 10.0, 500, 25, 50, "barren", 0.1,
     (7.0, 9.5), (0.05, 1.5), (5, 25)),
    # Boreal: acidic, high OC
    ("Finnish Taiga", 63.0, 26.0, 100, 2, 600, "forest", 0.6,
     (3.5, 6.5), (2.0, 10.0), (10, 40)),
    # Mediterranean: moderate
    ("Tuscany", 43.0, 11.0, 200, 14, 800, "cropland", 0.5,
     (6.0, 8.5), (0.5, 3.0), (15, 45)),
    # Tropical monsoon: high clay
    ("Indian Deccan", 18.0, 76.0, 500, 27, 700, "cropland", 0.4,
     (6.0, 8.5), (0.3, 2.5), (20, 60)),
    # Pacific Northwest: acidic, high OC
    ("Oregon Coast", 44.0, -124.0, 50, 10, 2000, "forest", 0.8,
     (3.5, 6.5), (2.0, 8.0), (15, 50)),
    # Steppe: neutral-alkaline, low clay
    ("Ukrainian Steppe", 48.0, 35.0, 150, 8, 500, "grassland", 0.4,
     (6.0, 8.5), (1.5, 5.0), (15, 40)),
    # Highland tropical: variable
    ("Ethiopian Highland", 9.0, 39.0, 2500, 15, 1100, "cropland", 0.4,
     (5.0, 7.5), (1.0, 5.0), (15, 50)),
    # Cold desert: alkaline, sandy
    ("Gobi Desert", 43.0, 105.0, 1000, 5, 150, "barren", 0.1,
     (7.0, 9.5), (0.1, 1.5), (5, 30)),
]


@pytest.fixture
def soil_model():
    return get_soil_model()


class TestSoilModelAccuracy:
    """Test soil model predictions against known reference values."""

    @pytest.mark.parametrize(
        "name,lat,lon,elev,temp,precip,cover,ndvi,ph_range,oc_range,clay_range",
        REFERENCE_LOCATIONS,
        ids=[loc[0] for loc in REFERENCE_LOCATIONS],
    )
    def test_ph_in_expected_range(
        self, soil_model, name, lat, lon, elev, temp, precip,
        cover, ndvi, ph_range, oc_range, clay_range,
    ) -> None:
        """Predicted pH should be within the expected range for each location."""
        result = soil_model.predict(
            latitude=lat, longitude=lon, elevation=elev,
            mean_temp=temp, mean_precip=precip,
            land_cover=cover, ndvi=ndvi,
        )
        ph = result["ph"]["value"]
        low, high = ph_range
        assert low <= ph <= high, (
            f"{name}: pH {ph} not in [{low}, {high}]"
        )

    @pytest.mark.parametrize(
        "name,lat,lon,elev,temp,precip,cover,ndvi,ph_range,oc_range,clay_range",
        REFERENCE_LOCATIONS,
        ids=[loc[0] for loc in REFERENCE_LOCATIONS],
    )
    def test_organic_carbon_in_expected_range(
        self, soil_model, name, lat, lon, elev, temp, precip,
        cover, ndvi, ph_range, oc_range, clay_range,
    ) -> None:
        """Predicted OC should be within the expected range for each location."""
        result = soil_model.predict(
            latitude=lat, longitude=lon, elevation=elev,
            mean_temp=temp, mean_precip=precip,
            land_cover=cover, ndvi=ndvi,
        )
        oc = result["organic_carbon_pct"]["value"]
        low, high = oc_range
        assert low <= oc <= high, (
            f"{name}: OC {oc}% not in [{low}, {high}]%"
        )

    @pytest.mark.parametrize(
        "name,lat,lon,elev,temp,precip,cover,ndvi,ph_range,oc_range,clay_range",
        REFERENCE_LOCATIONS,
        ids=[loc[0] for loc in REFERENCE_LOCATIONS],
    )
    def test_clay_in_expected_range(
        self, soil_model, name, lat, lon, elev, temp, precip,
        cover, ndvi, ph_range, oc_range, clay_range,
    ) -> None:
        """Predicted clay % should be within the expected range."""
        result = soil_model.predict(
            latitude=lat, longitude=lon, elevation=elev,
            mean_temp=temp, mean_precip=precip,
            land_cover=cover, ndvi=ndvi,
        )
        clay = result["texture"]["clay_pct"]
        low, high = clay_range
        assert low <= clay <= high, (
            f"{name}: clay {clay}% not in [{low}, {high}]%"
        )


class TestSoilModelConsistency:
    """Test that soil model predictions are internally consistent."""

    def test_texture_sums_to_100(self, soil_model) -> None:
        """Sand + silt + clay should sum to 100%."""
        for lat in range(-60, 70, 30):
            for lon in range(-180, 180, 60):
                result = soil_model.predict(latitude=float(lat), longitude=float(lon))
                texture = result["texture"]
                total = texture["sand_pct"] + texture["silt_pct"] + texture["clay_pct"]
                assert abs(total - 100.0) < 1.0, (
                    f"({lat},{lon}): texture sums to {total}"
                )

    def test_ph_within_natural_range(self, soil_model) -> None:
        """pH should always be between 3.5 and 9.5."""
        for lat in range(-60, 70, 20):
            for lon in range(-180, 180, 40):
                result = soil_model.predict(latitude=float(lat), longitude=float(lon))
                ph = result["ph"]["value"]
                assert 3.5 <= ph <= 9.5, f"({lat},{lon}): pH = {ph}"

    def test_organic_carbon_non_negative(self, soil_model) -> None:
        """Organic carbon should always be non-negative."""
        for lat in range(-60, 70, 20):
            for lon in range(-180, 180, 40):
                result = soil_model.predict(latitude=float(lat), longitude=float(lon))
                oc = result["organic_carbon_pct"]["value"]
                assert oc >= 0, f"({lat},{lon}): OC = {oc}"

    def test_bulk_density_physical_range(self, soil_model) -> None:
        """Bulk density should be between 0.8 and 1.8 g/cm³."""
        for lat in range(-60, 70, 20):
            for lon in range(-180, 180, 40):
                result = soil_model.predict(latitude=float(lat), longitude=float(lon))
                bd = result["bulk_density_gcm3"]
                assert 0.8 <= bd <= 1.8, f"({lat},{lon}): BD = {bd}"


class TestSoilModelConfidence:
    """Test that confidence scores are calibrated."""

    def test_analytical_confidence_below_threshold(self, soil_model) -> None:
        """Analytical model confidence should be below 0.5 to reflect uncertainty."""
        if soil_model.is_trained:
            pytest.skip("Only applies to analytical fallback")
        result = soil_model.predict(latitude=40.0, longitude=-90.0)
        ph_conf = result["ph"]["confidence"]
        assert ph_conf < 0.5, (
            f"Analytical confidence should be <0.5, got {ph_conf}"
        )

    def test_confidence_non_negative(self, soil_model) -> None:
        """All confidence scores should be non-negative."""
        result = soil_model.predict(latitude=40.0, longitude=-90.0)
        assert result["ph"]["confidence"] >= 0
        assert result["organic_carbon_pct"]["confidence"] >= 0
        assert result["nitrogen_pct"]["confidence"] >= 0
        assert result["moisture_pct"]["confidence"] >= 0

    def test_validation_status_present(self, soil_model) -> None:
        """Analytical model output should include validation status."""
        if soil_model.is_trained:
            pytest.skip("Only applies to analytical fallback")
        result = soil_model.predict(latitude=40.0, longitude=-90.0)
        assert "_validation_status" in result
        assert "unvalidated" in result["_validation_status"]


class TestSoilModelCorrelations:
    """Test that soil property predictions follow known correlations."""

    def test_wet_climate_lower_ph(self, soil_model) -> None:
        """Wetter climates should produce lower pH (more leaching)."""
        dry = soil_model.predict(
            latitude=30.0, longitude=0.0, mean_precip=200.0, mean_temp=20.0,
        )
        wet = soil_model.predict(
            latitude=30.0, longitude=0.0, mean_precip=2000.0, mean_temp=20.0,
        )
        assert wet["ph"]["value"] < dry["ph"]["value"], (
            f"Wet pH ({wet['ph']['value']}) should be < dry pH ({dry['ph']['value']})"
        )

    def test_cold_wet_higher_oc(self, soil_model) -> None:
        """Cold, wet conditions should accumulate more organic carbon."""
        warm_dry = soil_model.predict(
            latitude=30.0, longitude=0.0, mean_temp=25.0, mean_precip=300.0,
            ndvi=0.3,
        )
        cold_wet = soil_model.predict(
            latitude=60.0, longitude=0.0, mean_temp=3.0, mean_precip=800.0,
            ndvi=0.6,
        )
        assert cold_wet["organic_carbon_pct"]["value"] > warm_dry["organic_carbon_pct"]["value"]

    def test_higher_clay_higher_cec(self, soil_model) -> None:
        """Higher clay content should correlate with higher CEC."""
        # Tropical (high clay) vs arid (sandy)
        tropical = soil_model.predict(
            latitude=0.0, longitude=25.0, mean_precip=2000.0, mean_temp=26.0,
        )
        arid = soil_model.predict(
            latitude=25.0, longitude=25.0, mean_precip=50.0, mean_temp=25.0,
        )
        if tropical["texture"]["clay_pct"] > arid["texture"]["clay_pct"]:
            assert tropical["cec_cmolkg"] > arid["cec_cmolkg"]
