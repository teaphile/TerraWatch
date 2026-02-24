"""Alert management service.

Manages real-time alert creation, broadcasting, and lifecycle
for earthquake, weather, and environmental risk events.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing real-time alerts.

    Provides alert creation, broadcasting via WebSocket,
    alert history, and lifecycle management.
    """

    def __init__(self, max_history: int = 500) -> None:
        """Initialize alert service.

        Args:
            max_history: Maximum number of alerts to keep in history.
        """
        self._alerts: deque = deque(maxlen=max_history)
        self._active_alerts: Dict[str, Dict[str, Any]] = {}
        self._subscribers: Set[Callable] = set()
        self._alert_counter = 0

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str = "",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
        ttl_hours: float = 24,
    ) -> Dict[str, Any]:
        """Create a new alert.

        Args:
            alert_type: Type of alert (earthquake, landslide, flood, fire, weather).
            severity: Severity level (critical, warning, watch, advisory).
            title: Alert title.
            description: Detailed description.
            latitude: Event latitude.
            longitude: Event longitude.
            radius_km: Affected radius in km.
            data: Additional data payload.
            ttl_hours: Hours until alert expires.

        Returns:
            Created alert dictionary.
        """
        self._alert_counter += 1
        now = datetime.now(timezone.utc)

        alert = {
            "id": f"alert-{self._alert_counter:06d}",
            "type": alert_type,
            "severity": severity,
            "title": title,
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "data": data or {},
            "is_active": True,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
        }

        self._alerts.appendleft(alert)
        self._active_alerts[alert["id"]] = alert

        # Broadcast asynchronously
        asyncio.ensure_future(self._broadcast(alert))

        logger.info(
            f"Alert created: [{severity.upper()}] {title}",
            extra={"alert_id": alert["id"], "type": alert_type},
        )

        return alert

    def get_active_alerts(
        self,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get currently active alerts.

        Args:
            alert_type: Filter by type.
            severity: Filter by severity.
            limit: Maximum number to return.

        Returns:
            List of active alert dictionaries.
        """
        self._expire_alerts()

        alerts = list(self._active_alerts.values())

        if alert_type:
            alerts = [a for a in alerts if a["type"] == alert_type]
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        # Sort by severity (critical first) then by time
        severity_order = {"critical": 0, "warning": 1, "watch": 2, "advisory": 3}
        alerts.sort(
            key=lambda a: (severity_order.get(a["severity"], 4), a["created_at"]),
        )

        return alerts[:limit]

    def get_alert_history(
        self,
        limit: int = 100,
        alert_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get alert history.

        Args:
            limit: Maximum alerts to return.
            alert_type: Filter by type.

        Returns:
            List of historical alerts (newest first).
        """
        alerts = list(self._alerts)
        if alert_type:
            alerts = [a for a in alerts if a["type"] == alert_type]
        return alerts[:limit]

    def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss/deactivate an alert.

        Args:
            alert_id: Alert ID to dismiss.

        Returns:
            True if alert was found and dismissed.
        """
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id]["is_active"] = False
            del self._active_alerts[alert_id]
            return True
        return False

    def subscribe(self, callback: Callable) -> None:
        """Subscribe to alert broadcasts.

        Args:
            callback: Async callable to receive alert dictionaries.
        """
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable) -> None:
        """Unsubscribe from alert broadcasts."""
        self._subscribers.discard(callback)

    async def _broadcast(self, alert: Dict[str, Any]) -> None:
        """Broadcast alert to all subscribers."""
        for callback in list(self._subscribers):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Alert broadcast failed: {e}")

    def _expire_alerts(self) -> None:
        """Remove expired alerts from active set."""
        now = datetime.now(timezone.utc).isoformat()
        expired = [
            aid for aid, alert in self._active_alerts.items()
            if alert.get("expires_at", "") < now
        ]
        for aid in expired:
            self._active_alerts[aid]["is_active"] = False
            del self._active_alerts[aid]

    @property
    def stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        self._expire_alerts()
        return {
            "total_alerts": len(self._alerts),
            "active_alerts": len(self._active_alerts),
            "subscribers": len(self._subscribers),
        }


_service_instance: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """Get or create singleton alert service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = AlertService()
    return _service_instance
