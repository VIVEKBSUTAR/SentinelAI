import asyncio
import json
from typing import List
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        text_data = json.dumps(message)
        # Avoid changing length of list during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_text(text_data)
            except Exception:
                self.disconnect(connection)

    def broadcast_threadsafe(self, message: dict):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

manager = ConnectionManager()
