"""
Tests for API endpoints.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_root_endpoint(client):
    resp = await client.get("/api/v1/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert data["name"] == "TerraWatch"


@pytest.mark.anyio
async def test_health_endpoint(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_soil_analyze(client):
    resp = await client.get("/api/v1/soil/analyze", params={"lat": 40.0, "lon": -95.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "data" in data


@pytest.mark.anyio
async def test_risk_all(client):
    resp = await client.get("/api/v1/risk/all", params={"lat": 35.0, "lon": 139.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"


@pytest.mark.anyio
async def test_risk_earthquakes(client):
    resp = await client.get("/api/v1/risk/earthquake/recent")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_alerts_active(client):
    resp = await client.get("/api/v1/alerts/active")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_export_soil_csv(client):
    resp = await client.get("/api/v1/export/soil/csv", params={"lat": 40.0, "lon": -95.0})
    assert resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
