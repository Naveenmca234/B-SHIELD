"""
WebSocket connection manager. Broadcasts real-time events to all
connected dashboard clients:
- AI detections / tracking updates
- Alerts
- Camera status changes
- Threat scores
- Visibility status
"""
import json
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("ibvap.ws")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message_type: str, payload: dict):
        message = json.dumps({"type": message_type, "data": payload}, default=str)
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for s in stale:
            self.disconnect(s)

    async def broadcast_alert(self, payload: dict):
        await self.broadcast("alert_created", payload)


manager = ConnectionManager()
ws_manager = manager
