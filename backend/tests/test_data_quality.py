"""
Tests for data quality and source tracking.

Validates that all API responses include proper data source
attribution and warnings when estimated data is used.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.soil_model import SoilPredictionModel, get_soil_model
from app.services.weather_service import WeatherService


class TestDataSourceTracking:
    """Verify that data source information is present in all responses."""

    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    async def client(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.anyio
    async def test_soil_response_has_data_quality(self, client):
        """Soil analysis must include data_quality section."""
        resp = await client.get("/api/v1/soil/analyze", params={"lat": 40.0, "lon": -95.0})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "data_quality" in data
        dq = data["data_quality"]
        assert "sources" in dq
        assert "warnings" in dq
        assert "soil_data_source" in dq
        assert "is_fully_real_data" in dq

    @pytest.mark.anyio
    async def test_risk_response_has_data_quality(self, client):
        """Risk assessment must include data_quality section."""
        resp = await client.get("/api/v1/risk/all", params={"lat": 35.0, "lon": 139.0})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "data_quality" in data
        dq = data["data_quality"]
        assert "sources" in dq
        assert "warnings" in dq
        assert "weather_source" in dq

    @pytest.mark.anyio
    async def test_data_quality_endpoint_exists(self, client):
        """Data quality endpoint must be accessible."""
        resp = await client.get("/api/v1/data-quality", params={"lat": 40.0, "lon": -95.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "sources" in data["data"]
        assert "warnings" in data["data"]
        assert "overall_quality" in data["data"]


class TestWeatherFallbackTransparency:
    """Verify that weather fallback values are clearly marked."""

    def test_estimated_weather_has_source_field(self):
        svc = WeatherService()
        result = svc._estimate_weather(40.0, -95.0)
        assert result["source"] == "estimated"
        assert "_warning" in result

    def test_estimated_climate_has_source_field(self):
        svc = WeatherService()
        result = svc._estimate_climate(40.0, -95.0)
        assert result["source"] in ("estimated", "climate_normals")
        assert "_warning" in result

    def test_estimated_weather_precipitation_uses_climate_normals(self):
        """Estimated weather now uses climate normals — precipitation should be realistic."""
        svc = WeatherService()
        result = svc._estimate_weather(40.0, -95.0)
        # Climate normals should give a positive precipitation estimate for US Midwest
        assert result["precipitation_mm"] > 0
        assert "climate normals" in result.get("_warning", "").lower()


class TestSoilModelTransparency:
    """Verify soil model honestly reports its capabilities."""

    def test_analytical_model_reports_source(self):
        model = get_soil_model()
        result = model.predict(latitude=40.0, longitude=-95.0)
        # If no trained model exists, it should report analytical
        if not model.is_trained:
            assert result.get("_data_source") == "analytical_estimation"
            assert "estimated" in result.get("_source_detail", "").lower()

    def test_analytical_confidence_is_lower(self):
        """Analytical estimation should report lower confidence than ISRIC data."""
        model = get_soil_model()
        if not model.is_trained:
            result = model.predict(latitude=40.0, longitude=-95.0)
            # Confidence should be < 0.5 for analytical estimation
            assert result["ph"]["confidence"] < 0.5

    def test_soil_model_is_trained_flag(self):
        """Verify is_trained correctly reflects model availability."""
        model = get_soil_model()
        # Check if model file exists
        from app.models.soil_model import MODEL_DIR
        model_path = MODEL_DIR / "soil_ensemble.joblib"
        assert model.is_trained == model_path.exists()


class TestSoilPropertyRanges:
    """Validate that soil property predictions are in physically valid ranges."""

    def setup_method(self):
        self.model = get_soil_model()

    def test_ph_range(self):
        """Soil pH must be between 3.0 and 10.0."""
        for lat, lon in [(0, 0), (60, 10), (-30, 150), (45, -90)]:
            result = self.model.predict(latitude=lat, longitude=lon)
            ph = result["ph"]["value"]
            assert 3.0 <= ph <= 10.0, f"pH {ph} out of range for ({lat}, {lon})"

    def test_organic_carbon_range(self):
        """Organic carbon must be between 0.01% and 15%."""
        for lat, lon in [(0, 0), (60, 10), (-30, 150)]:
            result = self.model.predict(latitude=lat, longitude=lon)
            oc = result["organic_carbon_pct"]["value"]
            assert 0.01 <= oc <= 15.0, f"OC {oc} out of range"

    def test_texture_sums_to_100(self):
        """Sand + silt + clay must sum to 100%."""
        for lat, lon in [(0, 0), (60, 10), (-30, 150), (45, -90), (25, 70)]:
            result = self.model.predict(latitude=lat, longitude=lon)
            tex = result["texture"]
            total = tex["sand_pct"] + tex["silt_pct"] + tex["clay_pct"]
            assert abs(total - 100.0) < 1.5, f"Texture sum {total} for ({lat}, {lon})"

    def test_bulk_density_range(self):
        """Bulk density must be between 0.5 and 2.0 g/cm³."""
        for lat, lon in [(0, 0), (60, 10), (-30, 150)]:
            result = self.model.predict(latitude=lat, longitude=lon)
            bd = result["bulk_density_gcm3"]
            assert 0.5 <= bd <= 2.0, f"Bulk density {bd} out of range"

    def test_nitrogen_range(self):
        """Nitrogen must be between 0.001% and 2%."""
        for lat, lon in [(0, 0), (60, 10), (-30, 150)]:
            result = self.model.predict(latitude=lat, longitude=lon)
            n = result["nitrogen_pct"]["value"]
            assert 0.001 <= n <= 2.0, f"Nitrogen {n} out of range"


class TestISRICConversion:
    """Test ISRIC SoilGrids data conversion to internal format."""

    def test_isric_data_conversion(self):
        from app.services.soil_service import SoilService
        svc = SoilService()

        # Simulate ISRIC SoilGrids response (raw units)
        isric_data = {
            "phh2o": 65,       # pH * 10 → 6.5
            "soc": 180,        # dg/kg → 1.8%
            "nitrogen": 150,   # cg/kg → 0.15%
            "sand": 400,       # g/kg → 40.0%
            "silt": 350,       # g/kg → 35.0%
            "clay": 250,       # g/kg → 25.0%
            "cec": 150,        # mmol(c)/kg → 15.0 cmol/kg
            "bdod": 135,       # cg/cm³ → 1.35 g/cm³
        }

        result = svc._isric_to_soil_props(isric_data)

        assert result["ph"]["value"] == 6.5
        assert result["organic_carbon_pct"]["value"] == 1.8
        assert result["nitrogen_pct"]["value"] == 0.15
        assert result["texture"]["sand_pct"] == 40.0
        assert result["texture"]["silt_pct"] == 35.0
        assert result["texture"]["clay_pct"] == 25.0
        assert result["cec_cmolkg"] == 15.0
        assert result["bulk_density_gcm3"] == 1.35
        assert result["_data_source"] == "isric_soilgrids"

    def test_isric_missing_fields_use_defaults(self):
        from app.services.soil_service import SoilService
        svc = SoilService()

        # Partial ISRIC data
        isric_data = {"phh2o": 70, "soc": 200}
        result = svc._isric_to_soil_props(isric_data)

        assert result["ph"]["value"] == 7.0
        assert result["organic_carbon_pct"]["value"] == 2.0
        # Defaults for missing fields
        assert result["texture"]["sand_pct"] == 40.0
        assert result["_data_source"] == "isric_soilgrids"


class TestRiskModelConsistency:
    """Verify risk model predictions are logically consistent."""

    def test_landslide_risk_monotonic_with_slope(self):
        """Increasing slope should generally increase landslide risk."""
        from app.models.landslide_model import get_landslide_model
        model = get_landslide_model()

        slopes = [5, 15, 30, 45]
        probs = []
        for s in slopes:
            r = model.predict(
                latitude=35.0, longitude=139.0, slope=s,
                rainfall_mm=50, soil_moisture=30, ndvi=0.5,
            )
            probs.append(r["probability"])

        # Generally increasing (allow small non-monotonicity)
        assert probs[-1] > probs[0], "45° slope should have higher risk than 5°"

    def test_flood_risk_monotonic_with_rainfall(self):
        """More rainfall should increase flood risk."""
        from app.models.flood_model import get_flood_model
        model = get_flood_model()

        dry = model.predict(
            latitude=30.0, longitude=-90.0, rainfall_mm_24h=5,
        )
        wet = model.predict(
            latitude=30.0, longitude=-90.0, rainfall_mm_24h=200,
        )
        assert wet["probability"] > dry["probability"]

    def test_fire_risk_responds_to_conditions(self):
        """Extreme fire weather should produce high risk."""
        from app.models.fire_model import get_fire_model
        model = get_fire_model()

        cool_wet = model.predict(
            latitude=45.0, longitude=-120.0,
            temperature_c=10, humidity_pct=90, wind_speed_kmh=5,
            soil_moisture=50, ndvi=0.8, rainfall_last_7d_mm=30,
            days_since_rain=1,
        )
        hot_dry = model.predict(
            latitude=35.0, longitude=-120.0,
            temperature_c=42, humidity_pct=8, wind_speed_kmh=50,
            soil_moisture=5, ndvi=0.2, rainfall_last_7d_mm=0,
            days_since_rain=30,
        )
        assert hot_dry["probability"] > cool_wet["probability"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
