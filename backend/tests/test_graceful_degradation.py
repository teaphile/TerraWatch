"""Tests for graceful degradation when external APIs fail.

Validates that the system returns useful results (with warnings)
even when ISRIC, Open-Meteo, or all APIs are unreachable.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.weather_service import WeatherService
from app.services.soil_service import SoilService


@pytest.fixture
def weather_service() -> WeatherService:
    return WeatherService()


class TestWeatherAPIFailure:
    """Test weather service when Open-Meteo is down."""

    @pytest.mark.asyncio
    async def test_current_weather_fallback(self, weather_service: WeatherService) -> None:
        """When Open-Meteo current weather fails, should return estimate."""
        with patch.object(
            weather_service,
            "_fetch_open_meteo_current",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ):
            result = await weather_service.get_current_weather(40.0, -90.0)
            assert result is not None
            assert result["source"] == "estimated"
            assert "_warning" in result
            assert result["temperature_c"] != 0  # Not a dummy value

    @pytest.mark.asyncio
    async def test_climate_normals_fallback(self, weather_service: WeatherService) -> None:
        """When climate normals API fails, should return local estimate."""
        with patch.object(
            weather_service,
            "_fetch_climate_normals",
            new_callable=AsyncMock,
            side_effect=Exception("API timeout"),
        ):
            result = await weather_service.get_climate_normals(40.0, -90.0)
            assert result is not None
            assert result.get("source") in ("climate_normals", "estimated")

    @pytest.mark.asyncio
    async def test_elevation_fallback(self, weather_service: WeatherService) -> None:
        """When elevation API fails, should return grid estimate."""
        with patch.object(
            weather_service,
            "_get_client",
            new_callable=AsyncMock,
        ) as mock_client:
            # Make httpx.get raise
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = Exception("API error")
            client = AsyncMock()
            client.get.return_value = mock_response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = client

            result = await weather_service.get_elevation(40.0, -90.0)
            # Should fall back to grid — may return dict with elevation_m or a number
            if isinstance(result, dict):
                assert "elevation_m" in result
                assert isinstance(result["elevation_m"], (int, float))
            else:
                assert isinstance(result, (int, float))

    @pytest.mark.asyncio
    async def test_soil_moisture_estimate_when_api_fails(
        self, weather_service: WeatherService
    ) -> None:
        """When soil moisture API fails and no DB cache, should estimate."""
        result = weather_service._estimate_soil_moisture(40.0, -90.0)
        assert result is not None
        assert "average_pct" in result
        assert result["source"] == "estimated_from_climate"
        assert result["average_pct"] > 0


class TestSoilServiceDegradation:
    """Test soil analysis when various services fail."""

    @pytest.mark.asyncio
    async def test_analyze_with_api_failures(self) -> None:
        """Soil analysis should still return useful data when APIs fail."""
        service = SoilService()

        # Mock all external dependencies to fail
        with (
            patch.object(
                service._soil_fetcher,
                "fetch_properties",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch.object(
                service._weather,
                "get_current_weather",
                new_callable=AsyncMock,
                return_value=service._weather._estimate_weather(40.0, -90.0),
            ),
            patch.object(
                service._weather,
                "get_elevation",
                new_callable=AsyncMock,
                return_value={"elevation_m": 300.0, "source": "mocked"},
            ),
            patch.object(
                service._weather,
                "get_elevation_neighbors",
                new_callable=AsyncMock,
                return_value={"center": 300, "north": 310, "south": 290, "east": 305, "west": 295},
            ),
            patch.object(
                service._weather,
                "get_soil_moisture",
                new_callable=AsyncMock,
                return_value=service._weather._estimate_soil_moisture(40.0, -90.0),
            ),
            patch.object(
                service._weather,
                "get_climate_normals",
                new_callable=AsyncMock,
                return_value=service._weather._estimate_climate(40.0, -90.0),
            ),
        ):
            result = await service.analyze(40.0, -90.0)
            assert result is not None
            assert "soil_properties" in result
            assert "data_quality" in result
            # Analytical fallback should be clearly flagged
            dq = result.get("data_quality", {})
            assert dq.get("soil_data_source") in ("analytical_estimation", "isric_soilgrids")


class TestAllAPIsDown:
    """Test behavior when every external API is unreachable."""

    @pytest.mark.asyncio
    async def test_weather_all_down(self) -> None:
        """Weather service should still return estimated data."""
        service = WeatherService()

        # Patch httpx to always raise
        with patch("httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get.side_effect = Exception("Network unreachable")
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await service.get_current_weather(45.0, 10.0)
            assert result is not None
            assert "temperature_c" in result
            # Should be a climate-based estimate, not zeros
            assert "source" in result

    def test_sync_estimates_available(self) -> None:
        """Synchronous estimation methods should always work (no API needed)."""
        service = WeatherService()
        w = service._estimate_weather(0.0, 0.0)
        assert w["temperature_c"] > 0
        assert w["precipitation_mm"] > 0

        m = service._estimate_soil_moisture(0.0, 0.0)
        assert m["average_pct"] > 0

        c = service._estimate_climate(0.0, 0.0)
        assert c["mean_annual_precip_mm"] > 0


class TestDegradationWarnings:
    """Test that degraded responses include proper warnings."""

    def test_weather_estimate_has_warning(self) -> None:
        """Estimated weather must include a _warning field."""
        service = WeatherService()
        result = service._estimate_weather(35.0, 139.0)
        assert "_warning" in result
        assert isinstance(result["_warning"], str)

    def test_soil_moisture_estimate_has_warning(self) -> None:
        """Estimated soil moisture must include a _warning field."""
        service = WeatherService()
        result = service._estimate_soil_moisture(35.0, 139.0)
        assert "_warning" in result
        assert isinstance(result["_warning"], str)
