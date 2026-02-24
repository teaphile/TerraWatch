"""Alert API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.services.alert_service import get_alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/active")
async def get_active_alerts(
    alert_type: Optional[str] = Query(None, description="Filter by type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Get currently active alerts.

    Returns active alerts filtered by type and/or severity.
    Alert types: earthquake, landslide, flood, fire, weather.
    Severities: critical, warning, watch, advisory.
    """
    service = get_alert_service()
    alerts = service.get_active_alerts(alert_type, severity, limit)
    return {
        "status": "success",
        "data": {
            "count": len(alerts),
            "alerts": alerts,
        },
    }


@router.get("/history")
async def get_alert_history(
    limit: int = Query(100, ge=1, le=500),
    alert_type: Optional[str] = None,
) -> dict:
    """Get alert history (newest first)."""
    service = get_alert_service()
    alerts = service.get_alert_history(limit, alert_type)
    return {
        "status": "success",
        "data": {
            "count": len(alerts),
            "alerts": alerts,
        },
    }


@router.delete("/{alert_id}")
async def dismiss_alert(alert_id: str) -> dict:
    """Dismiss/deactivate an alert by ID."""
    service = get_alert_service()
    if service.dismiss_alert(alert_id):
        return {"status": "success", "message": f"Alert {alert_id} dismissed"}
    raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
