"""Unity 3D simulation bridge.

Manages WebSocket connections from Unity clients and provides
a thread-safe method to broadcast tracking data to them.
"""

import asyncio
import json
from typing import List
from fastapi import WebSocket

from src.core.logger import setup_logger

log = setup_logger("unity_bridge")


class UnityConnectionManager:
    """Manages WebSocket connections from Unity simulation clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info(f"Unity client connected ({len(self.active_connections)} total)")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    @property
    def has_clients(self) -> bool:
        return len(self.active_connections) > 0

    async def broadcast(self, message: dict):
        text_data = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(text_data)
            except Exception:
                self.disconnect(connection)

    def broadcast_threadsafe(self, message: dict):
        """Call from pipeline threads to send data to Unity."""
        if not self.has_clients:
            return  # skip serialization if no Unity clients
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    def send_tracking_update(self, person_id: int, x: float, y: float,
                              camera_id: str, threat_level: str = "normal",
                              timestamp: float = 0.0):
        """Send a person's position to Unity.

        Args:
            person_id: Stable ReID person identifier.
            x: Normalized X position (0-1) within the camera frame.
            y: Normalized Y position (0-1) within the camera frame.
            camera_id: Which camera is seeing this person.
            threat_level: Current threat level (normal/elevated/high/critical).
            timestamp: Unix timestamp.
        """
        self.broadcast_threadsafe({
            "type": "tracking_update",
            "data": {
                "person_id": person_id,
                "x": round(x, 4),
                "y": round(y, 4),
                "camera_id": camera_id,
                "threat_level": threat_level,
                "timestamp": round(timestamp, 3),
            }
        })


unity_manager = UnityConnectionManager()
