"""WebSocket handlers for real-time alert streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.alert_service import get_alert_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# Active WebSocket connections
_connections: Set[WebSocket] = set()


async def broadcast_alert(alert: dict) -> None:
    """Broadcast alert to all connected WebSocket clients.

    Args:
        alert: Alert dictionary to broadcast.
    """
    message = json.dumps({"type": "alert", "data": alert})
    disconnected = set()

    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)

    _connections.difference_update(disconnected)


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time alert streaming.

    Clients connect to receive real-time alerts as they are generated.
    Sends a welcome message on connection and then streams alerts.
    """
    await websocket.accept()
    _connections.add(websocket)

    # Register broadcaster with alert service
    alert_service = get_alert_service()
    alert_service.subscribe(broadcast_alert)

    try:
        # Send current active alerts on connect
        active = alert_service.get_active_alerts(limit=20)
        await websocket.send_text(json.dumps({
            "type": "initial",
            "data": {"active_alerts": active},
        }))

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                # Handle ping
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        _connections.discard(websocket)
        if not _connections:
            alert_service.unsubscribe(broadcast_alert)
